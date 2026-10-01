"""Import market values from the public Transfermarkt dataset (dcaribou/transfermarkt-datasets).

Expects a directory with players.csv, player_valuations.csv and (optional, for club
matching) clubs.csv; `.csv.gz` also works. The dataset is CC0. It only holds the *current*
contract expiry per player, so contracts are not imported (they would be wrong for past seasons).
"""

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .lookup import normalize
from .values import VALUE_COLS, season_end, store_values

PROVIDER = "transfermarkt-dataset"
GENERIC_CLUB_WORDS = {"club", "football", "futbol", "fc", "cf", "ac", "as", "sc", "united",
                      "city", "real", "de", "the", "sporting", "association", "calcio"}


def read_table(directory: Path, name: str, required: bool = True) -> pd.DataFrame | None:
    for suffix in (".csv", ".csv.gz"):
        path = Path(directory) / f"{name}{suffix}"
        if path.exists():
            return pd.read_csv(path)
    if required:
        raise FileNotFoundError(f"{name}.csv(.gz) not found in {directory}")
    return None


def tokens(text) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize(text)))


def club_words(name) -> set[str]:
    return {t for t in tokens(name) if t not in GENERIC_CLUB_WORDS and len(t) > 2}


def tm_club_index(valuations: pd.DataFrame, players: pd.DataFrame,
                  clubs: pd.DataFrame | None) -> dict[int, set[str]]:
    """tm player_id -> club-name words of every club seen in valuations (+ current club)."""
    names: dict[int, set[str]] = defaultdict(set)
    if clubs is not None and "current_club_id" in valuations.columns:
        club_name = dict(zip(clubs["club_id"], clubs["name"], strict=True))
        for pid, cid in valuations[["player_id", "current_club_id"]].drop_duplicates().itertuples(
                index=False):
            names[pid] |= club_words(club_name.get(cid))
    if "current_club_name" in players.columns:
        for pid, cname in zip(players["player_id"], players["current_club_name"], strict=True):
            names[pid] |= club_words(cname)
    return names


def match_to_tm(sb_players: pd.DataFrame, tm_players: pd.DataFrame,
                tm_clubs: dict[int, set[str]]) -> dict[int, int]:
    """StatsBomb player_id -> Transfermarkt player_id.

    `sb_players` has player_id, player_name, player_nickname, teams. A TM player matches
    when all words of its name occur in the StatsBomb name/nickname, and (when club info
    exists) one of its clubs shares a word with the StatsBomb teams. Ambiguity -> skipped.
    """
    by_surname: dict[str, list[tuple[int, set[str]]]] = defaultdict(list)
    for pid, name in zip(tm_players["player_id"], tm_players["name"], strict=True):
        toks = re.findall(r"[a-z0-9]+", normalize(name))
        if toks:
            by_surname[toks[-1]].append((pid, set(toks)))
    result = {}
    for r in sb_players.itertuples(index=False):
        sb_tokens = tokens(r.player_name) | tokens(r.player_nickname)
        team_words = club_words(r.teams)
        found = {pid for tok in sb_tokens for pid, toks in by_surname.get(tok, [])
                 if toks <= sb_tokens}
        found = {pid for pid in found
                 if not tm_clubs.get(pid) or tm_clubs[pid] & team_words}
        if len(found) == 1:
            result[r.player_id] = found.pop()
    return result


def value_rows(valuations: pd.DataFrame, id_map: dict[int, int], seasons: list[str],
               window_days: int = 365, source: str = "statsbomb") -> pd.DataFrame:
    """Valuations of matched players within `window_days` of any given season end."""
    tm_to_sb = {tm: sb for sb, tm in id_map.items()}
    v = valuations[valuations["player_id"].isin(tm_to_sb)].copy()
    v["date"] = pd.to_datetime(v["date"])
    ends = [season_end(s) for s in seasons]
    keep = pd.Series(False, index=v.index)
    for end in ends:
        keep |= (v["date"] - end).abs() <= pd.Timedelta(days=window_days)
    v = v[keep & v["market_value_in_eur"].notna()]
    out = pd.DataFrame({
        "source": source, "player_id": v["player_id"].map(tm_to_sb),
        "as_of_date": v["date"].dt.date, "market_value_eur": v["market_value_in_eur"].astype(float),
        "contract_until": None, "provider": PROVIDER, "notes": None,
    })
    return out[VALUE_COLS].drop_duplicates(["player_id", "as_of_date"])


def import_transfermarkt(con, directory, window_days: int = 365) -> dict:
    """Match players, load valuations near the ingested seasons. Returns coverage numbers."""
    tm_players = read_table(directory, "players")
    valuations = read_table(directory, "player_valuations")
    clubs = read_table(directory, "clubs", required=False)
    sb = con.execute("""SELECT p.player_id, p.player_name, p.player_nickname,
                               string_agg(DISTINCT s.teams, ', ') AS teams
                        FROM players p JOIN player_season_stats s USING (source, player_id)
                        WHERE p.source = 'statsbomb' GROUP BY ALL""").df()
    seasons = [r[0] for r in con.execute(
        "SELECT DISTINCT season_name FROM player_season_stats").fetchall()]
    id_map = match_to_tm(sb, tm_players, tm_club_index(valuations, tm_players, clubs))
    rows = value_rows(valuations, id_map, seasons, window_days)
    store_values(con, rows)
    return {"players": len(sb), "matched": len(id_map), "valuations": len(rows),
            "with_value": rows["player_id"].nunique()}
