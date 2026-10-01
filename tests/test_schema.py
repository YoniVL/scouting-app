from scouting.db import connect


def test_schema_creates_tables_and_market_values_is_empty():
    con = connect(":memory:")
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert {"matches", "players", "player_minutes", "events", "player_season_stats",
            "market_values"} <= tables
    assert con.execute("SELECT count(*) FROM market_values").fetchone()[0] == 0
