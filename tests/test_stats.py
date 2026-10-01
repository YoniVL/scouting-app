import pandas as pd

from scouting.db import connect
from scouting.stats import build_player_season_stats, event_counts, progressive_mask


def moves(rows):
    return pd.DataFrame(rows, columns=["x", "y", "end_x", "end_y"])


def test_progressive_mask():
    df = moves([
        (30, 40, 60, 40),    # own half -> halfway: 30 closer, > 25% of 90 -> yes
        (20, 40, 50, 40),    # stays in own half -> no
        (70, 40, 75, 40),    # only 5 closer -> no
        (70, 40, 90, 40),    # 20 closer, needs max(10, 12.5) -> yes
        (100, 40, 105, 40),  # 5 closer -> no
        (100, 40, 111, 40),  # 11 closer, needs 10 -> yes
    ])
    assert progressive_mask(df).tolist() == [True, False, False, True, False, True]


def event(player, typ, role="CM", sub=None, outcome=None, x=70, y=40, ex=95, ey=40, xg=None):
    return {"source": "s", "player_id": player, "season_name": "2015/2016", "role": role,
            "type": typ, "sub_type": sub, "outcome": outcome, "x": x, "y": y,
            "end_x": ex, "end_y": ey, "xg": xg}


def test_event_counts():
    ev = pd.DataFrame([
        event(1, "Pass"),                                  # progressive, completed
        event(1, "Pass", outcome="Incomplete"),            # not progressive (failed)
        event(1, "Pass", sub="Throw-in"),                  # excluded set piece
        event(1, "Carry"),                                 # progressive carry
        event(1, "Shot", xg=0.2),
        event(1, "Shot", sub="Penalty", xg=0.76),          # penalty ignored
        event(1, "Duel", sub="Tackle"),
        event(1, "Duel", sub="Aerial Lost"),
        event(1, "Interception"),
        event(1, "Pressure"),
    ])
    row = event_counts(ev).iloc[0]
    assert (row.passes, row.progressive_passes) == (3, 1)
    assert (row.carries, row.progressive_carries) == (1, 1)
    assert (row.shots, row.npxg) == (1, 0.2)
    assert (row.tackles, row.interceptions, row.pressures) == (1, 1, 1)


def test_build_player_season_stats_end_to_end():
    con = connect(":memory:")
    con.execute("INSERT INTO matches VALUES ('s',1,2,'PL',27,'2015/2016',NULL,'A','B',0,0)")
    con.execute("INSERT INTO players VALUES ('s',10,'Ann',NULL),('s',11,'Gk',NULL)")
    con.execute("""INSERT INTO player_minutes VALUES
        ('s',1,10,'A','Center Midfield','CM',90),('s',1,10,'A','Right Wing','W',45),
        ('s',1,11,'A','Goalkeeper','GK',90)""")
    con.execute("""INSERT INTO events VALUES
        ('s',1,1,1,1,0,'Pressure',NULL,NULL,'A',10,'Center Midfield','CM',50,40,NULL,NULL,NULL)""")
    assert build_player_season_stats(con) == 2  # GK excluded; CM and W rows for player 10
    rows = con.execute("""SELECT role, minutes, pressures, pressures_p90
                          FROM player_season_stats ORDER BY role""").fetchall()
    assert rows == [("CM", 90.0, 1.0, 1.0), ("W", 45.0, 0.0, 0.0)]
