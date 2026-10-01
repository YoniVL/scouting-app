"""Market value / contract data (phase 2): CSV import, season matching, undervalued score.

CSV columns: player_name, as_of_date, market_value_eur; optional: club, contract_until,
provider, notes. Source of the numbers is the user's own file (e.g. a Transfermarkt export).
"""

import re

import numpy as np
import pandas as pd

from .lookup import find_players, normalize
from .percentiles import PCT_COLS, percentile_of

REQUIRED = ["player_name", "as_of_date", "market_value_eur"]
VALUE_COLS = ["source", "player_id", "as_of_date", "market_value_eur", "contract_until",
              "provider", "notes"]


def parse_amount(text: str | float) -> float:
    """'10m' -> 1e7, '500k' -> 5e5, '2.5m' -> 2.5e6, plain numbers pass through."""
    if isinstance(text, (int, float)):
        return float(text)
    m = re.fullmatch(r"\s*([\d.,]+)\s*([kKmM]?)\s*", text)
    if not m:
        raise ValueError(f"Cannot parse amount: {text!r}")
    num = float(m.group(1).replace(",", "."))
    return num * {"": 1, "k": 1e3, "m": 1e6}[m.group(2).lower()]


def season_end(season_name: str) -> pd.Timestamp:
    """'2015/2016' -> 2016-06-30; '2018' -> 2018-06-30 (end year, mid-year)."""
    return pd.Timestamp(year=int(season_name[-4:]), month=6, day=30)


def match_player(players: pd.DataFrame, clubs: pd.DataFrame, name: str, club: str | None):
    """Return player_id for a CSV row, or None when no/ambiguous match.

    `clubs` has (player_id, team) pairs; the club column breaks ties between namesakes.
    """
    found = find_players(players, name)
    if len(found) > 1 and club:
        c = normalize(club)
        teams = clubs[clubs["team"].map(lambda t: c in normalize(t) or normalize(t) in c)]
        found = found[found["player_id"].isin(teams["player_id"])]
    return int(found["player_id"].iloc[0]) if len(found) == 1 else None


def import_values(con, csv_path, source: str = "statsbomb") -> dict:
    """Load a CSV into market_values. Returns counts and the unmatched/ambiguous names."""
    df = pd.read_csv(csv_path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")
    players = con.execute("SELECT * FROM players WHERE source = ?", [source]).df()
    clubs = con.execute("SELECT DISTINCT player_id, team FROM player_minutes WHERE source = ?",
                        [source]).df()
    rows, unmatched = [], []
    for r in df.to_dict("records"):
        pid = match_player(players, clubs, r["player_name"], r.get("club"))
        if pid is None:
            unmatched.append(r["player_name"])
            continue
        rows.append({
            "source": source, "player_id": pid,
            "as_of_date": pd.to_datetime(r["as_of_date"]).date(),
            "market_value_eur": parse_amount(r["market_value_eur"]),
            "contract_until": (pd.to_datetime(r["contract_until"]).date()
                               if pd.notna(r.get("contract_until")) else None),
            "provider": r.get("provider") if pd.notna(r.get("provider")) else "csv",
            "notes": r.get("notes") if pd.notna(r.get("notes")) else None,
        })
    out = pd.DataFrame(rows, columns=VALUE_COLS)
    store_values(con, out)
    return {"imported": len(out), "unmatched": sorted(set(unmatched))}


def store_values(con, out: pd.DataFrame) -> None:
    """Upsert rows (VALUE_COLS) into market_values, replacing same player/date/provider."""
    if out.empty:
        return
    con.register("_vals", out)
    con.execute("""DELETE FROM market_values USING _vals v WHERE market_values.source = v.source
                   AND market_values.player_id = v.player_id
                   AND market_values.as_of_date = v.as_of_date
                   AND market_values.provider = v.provider""")
    con.execute("INSERT INTO market_values SELECT * FROM _vals")
    con.unregister("_vals")


def attach_values(stats: pd.DataFrame, values: pd.DataFrame) -> pd.DataFrame:
    """Add `market_value_eur`, `contract_until`, `value_date` per row.

    Uses the value whose date is closest to the end of the row's season.
    """
    out = stats.copy()
    keys = ["source", "player_id", "season_name"]
    if values.empty:
        return out.assign(market_value_eur=np.nan, contract_until=pd.NaT, value_date=pd.NaT)
    ends = out[keys].drop_duplicates()
    ends["_end"] = ends["season_name"].map(season_end)
    v = values.rename(columns={"as_of_date": "value_date"})
    v["value_date"] = pd.to_datetime(v["value_date"])
    cand = ends.merge(v, on=["source", "player_id"])
    cand["_gap"] = (cand["value_date"] - cand["_end"]).abs()
    best = cand.sort_values("_gap").drop_duplicates(keys)[
        keys + ["market_value_eur", "contract_until", "value_date"]]
    best["contract_until"] = pd.to_datetime(best["contract_until"])
    return out.merge(best, on=keys, how="left")


def undervalued_scores(pct: pd.DataFrame) -> pd.DataFrame:
    """Add `performance`, `perf_rank`, `value_rank`, `undervalued` (-100..100).

    performance = mean of the percentile columns. Ranks are taken within (season, role)
    among eligible players that have a value; undervalued = perf_rank - value_rank.
    """
    out = pct.copy()
    out["performance"] = out[PCT_COLS].mean(axis=1)
    for col in ("perf_rank", "value_rank", "undervalued"):
        out[col] = np.nan
    has_value = out["market_value_eur"].notna()
    for idx in out[has_value].groupby(["season_name", "role"]).groups.values():
        grp = out.loc[idx]
        pool = grp[grp["eligible"]]
        if pool.empty:
            continue
        out.loc[idx, "perf_rank"] = percentile_of(grp["performance"].to_numpy(),
                                                  pool["performance"].to_numpy())
        out.loc[idx, "value_rank"] = percentile_of(np.log1p(grp["market_value_eur"].to_numpy()),
                                                   np.log1p(pool["market_value_eur"].to_numpy()))
    out["undervalued"] = out["perf_rank"] - out["value_rank"]
    return out


def filter_by_value(df: pd.DataFrame, max_value: float | None = None,
                    contract_before: pd.Timestamp | None = None) -> pd.DataFrame:
    """Keep rows within the value / contract limits. Rows lacking the data are dropped."""
    if max_value is not None:
        df = df[df["market_value_eur"] <= max_value]
    if contract_before is not None:
        df = df[df["contract_until"] < contract_before]
    return df


def format_eur(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"€{value / 1e6:.1f}m" if value >= 1e6 else f"€{value / 1e3:.0f}k"
