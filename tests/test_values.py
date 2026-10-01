import pandas as pd
import pytest

from scouting.db import connect
from scouting.percentiles import PCT_COLS
from scouting.values import (
    attach_values,
    filter_by_value,
    format_eur,
    import_values,
    parse_amount,
    season_end,
    undervalued_scores,
)


def test_parse_amount_and_format():
    assert parse_amount("10m") == 1e7 and parse_amount("500k") == 5e5
    assert parse_amount("2,5m") == 2.5e6 and parse_amount(1234) == 1234.0
    with pytest.raises(ValueError):
        parse_amount("lots")
    assert format_eur(2.5e6) == "€2.5m" and format_eur(300000) == "€300k"
    assert format_eur(float("nan")) == "n/a"


def test_season_end():
    assert season_end("2015/2016") == pd.Timestamp("2016-06-30")


def seed(con):
    con.execute("""INSERT INTO players VALUES ('statsbomb',1,'Jamie Richard Vardy',NULL),
        ('statsbomb',2,'John Smith',NULL),('statsbomb',3,'John Smith',NULL)""")
    con.execute("""INSERT INTO player_minutes VALUES ('statsbomb',1,2,'Arsenal','Left Back','FB',90),
        ('statsbomb',1,3,'Chelsea','Left Back','FB',90)""")


def test_import_matches_names_clubs_and_reports_unmatched(tmp_path):
    con = connect(":memory:")
    seed(con)
    csv = tmp_path / "v.csv"
    csv.write_text(
        "player_name,club,as_of_date,market_value_eur,contract_until\n"
        "Jamie Vardy,Leicester,2016-06-01,15m,2018-06-30\n"
        "John Smith,Chelsea FC,2016-06-01,2m,\n"
        "John Smith,,2016-06-01,1m,\n"        # ambiguous without club
        "Nobody Here,,2016-06-01,1m,\n")
    res = import_values(con, csv)
    assert res["imported"] == 2 and res["unmatched"] == ["John Smith", "Nobody Here"]
    rows = con.execute("SELECT player_id, market_value_eur FROM market_values "
                       "ORDER BY player_id").fetchall()
    assert rows == [(1, 15e6), (3, 2e6)]
    assert import_values(con, csv)["imported"] == 2  # re-import replaces, no duplicates
    assert con.execute("SELECT count(*) FROM market_values").fetchone()[0] == 2


def test_attach_picks_value_closest_to_season_end():
    stats = pd.DataFrame({"source": ["s"], "player_id": [1], "season_name": ["2015/2016"]})
    values = pd.DataFrame({
        "source": ["s", "s"], "player_id": [1, 1],
        "as_of_date": ["2015-09-01", "2016-05-20"], "market_value_eur": [5e6, 9e6],
        "contract_until": ["2018-06-30", "2018-06-30"]})
    out = attach_values(stats, values)
    assert out["market_value_eur"].iloc[0] == 9e6
    assert attach_values(stats, values.iloc[0:0])["market_value_eur"].isna().all()


def test_undervalued_and_filters():
    rows = [{"season_name": "2015/2016", "role": "ST", "eligible": True,
             "market_value_eur": v, **dict.fromkeys(PCT_COLS, p)}
            for v, p in [(1e6, 90), (50e6, 90), (50e6, 10), (None, 99)]]
    df = undervalued_scores(pd.DataFrame(rows))
    assert df["undervalued"].iloc[0] > df["undervalued"].iloc[1]  # same output, cheaper
    assert df["undervalued"].iloc[3] != df["undervalued"].iloc[3]  # no value -> NaN
    df["contract_until"] = pd.to_datetime(["2017-06-30", "2020-06-30", "2016-06-30", None])
    kept = filter_by_value(df, max_value=10e6, contract_before=pd.Timestamp("2018-01-01"))
    assert len(kept) == 1 and kept["market_value_eur"].iloc[0] == 1e6
