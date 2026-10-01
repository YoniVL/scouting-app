"""Load matches from a Source into DuckDB (idempotent per match)."""

from concurrent.futures import ThreadPoolExecutor

import duckdb
import pandas as pd

from .minutes import add_minutes
from .roles import position_to_role
from .sources.base import MatchData, Source


def ingested_match_ids(con: duckdb.DuckDBPyConnection, source: str) -> set[int]:
    rows = con.execute("SELECT match_id FROM matches WHERE source = ?", [source]).fetchall()
    return {r[0] for r in rows}


def build_minutes_frame(data: MatchData) -> pd.DataFrame:
    """Stints with minutes and role; unplayed bench entries (0 minutes) dropped."""
    out = add_minutes(data.stints, data.period_ends)
    out["role"] = out["position"].map(position_to_role)
    return out[out["minutes"] > 0][["player_id", "team", "position", "role", "minutes"]]


def _insert(con, table: str, source: str, match_id: int | None, df: pd.DataFrame) -> None:
    """Append `df` to `table`, prefixing source (and match_id) columns."""
    if df.empty:
        return
    df = df.copy()
    if match_id is not None:
        df.insert(0, "match_id", match_id)
    df.insert(0, "source", source)
    con.register("_tmp", df)
    cols = ", ".join(df.columns)
    con.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _tmp")
    con.unregister("_tmp")


def store_match(con, source: str, match_row: pd.Series, data: MatchData) -> None:
    """Write one match atomically; the `matches` row goes in last as the 'done' marker."""
    mid = int(match_row["match_id"])
    con.execute("BEGIN")
    try:
        _insert(con, "events", source, mid, data.events)
        _insert(con, "player_minutes", source, mid, build_minutes_frame(data))
        players = data.players.drop_duplicates("player_id")
        known = {r[0] for r in con.execute(
            "SELECT player_id FROM players WHERE source = ?", [source]).fetchall()}
        _insert(con, "players", source, None, players[~players["player_id"].isin(known)])
        _insert(con, "matches", source, None, match_row.to_frame().T)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def ingest(con, source: Source, selection: list[tuple[int, int]], workers: int = 8,
           progress=lambda done, total: None) -> int:
    """Ingest all not-yet-loaded matches for (competition_id, season_id) pairs.

    Downloads run in parallel; database writes stay on this thread. Returns matches loaded.
    """
    done_ids = ingested_match_ids(con, source.name)
    todo = []
    for comp_id, season_id in selection:
        matches = source.fetch_matches(comp_id, season_id)
        todo += [r for _, r in matches.iterrows() if int(r["match_id"]) not in done_ids]
    with ThreadPoolExecutor(workers) as pool:
        results = pool.map(lambda r: (r, source.fetch_match_data(int(r["match_id"]))), todo)
        for i, (row, data) in enumerate(results, 1):
            store_match(con, source.name, row, data)
            progress(i, len(todo))
    return len(todo)
