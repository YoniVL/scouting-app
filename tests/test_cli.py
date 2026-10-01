import pandas as pd
from typer.testing import CliRunner

from scouting.cli import app
from scouting.db import connect
from scouting.stats import COUNT_STATS, P90_STATS

runner = CliRunner()


def seed(path):
    con = connect(path)
    con.execute("INSERT INTO matches VALUES ('statsbomb',1,2,'PL',27,'2015/2016',NULL,'A','B',0,0)")
    rows = []
    for pid in range(1, 7):
        con.execute("INSERT INTO players VALUES ('statsbomb', ?, ?, NULL)", [pid, f"Player{pid} Müller"])
        rows.append({"source": "statsbomb", "player_id": pid, "player_name": f"Player{pid} Müller",
                     "season_name": "2015/2016", "role": "ST", "teams": "A",
                     "competitions": "PL", "matches": 10,
                     "minutes": 2000.0 if pid != 6 else 200.0,
                     **{c: float(pid) for c in COUNT_STATS},
                     **{c: float((pid * 7) % 5 + pid % 3) for c in P90_STATS}})
    df = pd.DataFrame(rows)
    con.register("_d", df)
    con.execute("INSERT INTO player_season_stats SELECT * FROM _d")
    con.close()


def test_profile_and_similar_with_small_sample_warning(tmp_path):
    db = str(tmp_path / "t.duckdb")
    seed(db)
    out = runner.invoke(app, ["profile", "player6", "--db", db]).output
    assert "Small sample" in out and "Pressures" in out
    out = runner.invoke(app, ["similar", "muller", "--top", "3", "--db", db])
    assert out.exit_code == 1 and "ambiguous" in out.output  # 6 players match "muller"
    out = runner.invoke(app, ["similar", "Player1", "--top", "3", "--db", db]).output
    assert "Similarity" in out and "Player6" not in out  # below minimum is no candidate


def test_unknown_player(tmp_path):
    db = str(tmp_path / "t.duckdb")
    seed(db)
    res = runner.invoke(app, ["profile", "nobody", "--db", db])
    assert res.exit_code == 1


def test_values_in_profile_similar_filters_and_undervalued(tmp_path):
    db = str(tmp_path / "t.duckdb")
    seed(db)
    csv = tmp_path / "v.csv"
    csv.write_text("player_name,as_of_date,market_value_eur,contract_until\n"
                   "Player1 Müller,2016-05-01,1m,2017-06-30\n"
                   "Player2 Müller,2016-05-01,30m,2020-06-30\n"
                   "Player3 Müller,2016-05-01,2m,2016-12-31\n"
                   "Ghost,2016-05-01,1m,\n")
    out = runner.invoke(app, ["import-values", str(csv), "--db", db]).output
    assert "Imported 3" in out and "Ghost" in out
    assert "€1.0m" in runner.invoke(app, ["profile", "Player1", "--db", db]).output
    out = runner.invoke(app, ["similar", "Player1", "--max-value", "5m",
                              "--contract-ends-before", "2018", "--db", db]).output
    assert "Player3" in out and "Player2" not in out
    out = runner.invoke(app, ["undervalued", "--db", db]).output
    assert "Score" in out and "Player1" in out
    assert "Player4" not in out  # no value imported -> not scored
