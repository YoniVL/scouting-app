"""Source-agnostic DuckDB schema.

Every table is keyed by (source, ...) so several data providers can live side by
side. Source modules map their raw data onto these tables (see sources/base.py).
"""

import duckdb

DDL = [
    """
    CREATE TABLE IF NOT EXISTS matches (
        source VARCHAR, match_id BIGINT,
        competition_id INTEGER, competition_name VARCHAR,
        season_id INTEGER, season_name VARCHAR,
        match_date DATE, home_team VARCHAR, away_team VARCHAR,
        home_score INTEGER, away_score INTEGER,
        PRIMARY KEY (source, match_id)
    )""",
    """
    CREATE TABLE IF NOT EXISTS players (
        source VARCHAR, player_id BIGINT, player_name VARCHAR, player_nickname VARCHAR,
        PRIMARY KEY (source, player_id)
    )""",
    # One row per position stint of a player in a match; minutes are derived.
    """
    CREATE TABLE IF NOT EXISTS player_minutes (
        source VARCHAR, match_id BIGINT, player_id BIGINT, team VARCHAR,
        position VARCHAR, role VARCHAR, minutes DOUBLE
    )""",
    # Slimmed-down event stream (only what the stats need).
    """
    CREATE TABLE IF NOT EXISTS events (
        source VARCHAR, match_id BIGINT, event_idx INTEGER,
        period INTEGER, minute INTEGER, second INTEGER,
        type VARCHAR, sub_type VARCHAR, outcome VARCHAR,
        team VARCHAR, player_id BIGINT, position VARCHAR, role VARCHAR,
        x DOUBLE, y DOUBLE, end_x DOUBLE, end_y DOUBLE, xg DOUBLE
    )""",
    # Derived: per player / season / role aggregates (rebuilt by `scout build`).
    """
    CREATE TABLE IF NOT EXISTS player_season_stats (
        source VARCHAR, player_id BIGINT, player_name VARCHAR,
        season_name VARCHAR, role VARCHAR, teams VARCHAR, competitions VARCHAR,
        matches INTEGER, minutes DOUBLE,
        passes DOUBLE, progressive_passes DOUBLE, carries DOUBLE, progressive_carries DOUBLE,
        shots DOUBLE, npxg DOUBLE, tackles DOUBLE, interceptions DOUBLE, pressures DOUBLE,
        passes_p90 DOUBLE, progressive_passes_p90 DOUBLE, carries_p90 DOUBLE,
        progressive_carries_p90 DOUBLE, shots_p90 DOUBLE, npxg_p90 DOUBLE,
        tackles_p90 DOUBLE, interceptions_p90 DOUBLE, pressures_p90 DOUBLE
    )""",
    # Phase 2 placeholder: intentionally left empty for now.
    """
    CREATE TABLE IF NOT EXISTS market_values (
        source VARCHAR, player_id BIGINT, as_of_date DATE,
        market_value_eur DOUBLE, contract_until DATE,
        provider VARCHAR, notes VARCHAR
    )""",
]


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in DDL:
        con.execute(stmt)
