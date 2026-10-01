import pandas as pd

from scouting.db import connect
from scouting.tm_dataset import import_transfermarkt

TM_PLAYERS = pd.DataFrame({
    "player_id": [100, 200, 201, 300],
    "name": ["Jamie Vardy", "Danilo", "Danilo", "Fred"],
    "current_club_name": ["Leicester City", "Real Madrid", "Porto", "Man Utd"],
})
TM_VALS = pd.DataFrame({
    "player_id": [100, 100, 100, 200, 201, 300],
    "date": ["2016-01-10", "2016-06-01", "2012-01-01", "2016-06-01", "2016-06-01", "2016-06-01"],
    "market_value_in_eur": [8e6, 10e6, 1e6, 20e6, 5e6, 7e6],
    "current_club_id": [1, 1, 9, 2, 3, 4],
})
TM_CLUBS = pd.DataFrame({"club_id": [1, 2, 3, 4],
                         "name": ["Leicester City", "Real Madrid CF", "FC Porto", "Fred FC"]})


def seed(con):
    con.execute("""INSERT INTO players VALUES
        ('statsbomb',1,'Jamie Richard Vardy',NULL),
        ('statsbomb',2,'Danilo Luiz da Silva',NULL),
        ('statsbomb',3,'Frederico Rodrigues',  'Fred'),
        ('statsbomb',4,'Unknown Person',NULL)""")
    for pid, team in [(1, "Leicester City"), (2, "Real Madrid"), (3, "Shakhtar"), (4, "X")]:
        con.execute("""INSERT INTO player_season_stats (source, player_id, season_name, role,
                       teams, minutes) VALUES ('statsbomb', ?, '2015/2016', 'CM', ?, 1000)""",
                    [pid, team])


def test_import_matches_by_name_and_club_and_filters_window(tmp_path):
    TM_PLAYERS.to_csv(tmp_path / "players.csv", index=False)
    TM_VALS.to_csv(tmp_path / "player_valuations.csv.gz", index=False)
    TM_CLUBS.to_csv(tmp_path / "clubs.csv", index=False)
    con = connect(":memory:")
    seed(con)
    res = import_transfermarkt(con, tmp_path)
    got = con.execute("""SELECT player_id, market_value_eur FROM market_values
                         ORDER BY player_id, as_of_date""").fetchall()
    # Vardy: 2012 value outside window; Danilo resolved to Real Madrid by club;
    # Fred (nickname) rejected because TM club "Fred FC" shares no word with "Shakhtar".
    assert got == [(1, 8e6), (1, 10e6), (2, 20e6)]
    assert res["matched"] == 2 and res["with_value"] == 2


def test_import_is_idempotent(tmp_path):
    TM_PLAYERS.to_csv(tmp_path / "players.csv", index=False)
    TM_VALS.to_csv(tmp_path / "player_valuations.csv", index=False)
    con = connect(":memory:")
    seed(con)
    import_transfermarkt(con, tmp_path)
    import_transfermarkt(con, tmp_path)
    assert con.execute("SELECT count(*) FROM market_values").fetchone()[0] == 3
