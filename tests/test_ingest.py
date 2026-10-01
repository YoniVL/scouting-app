import pandas as pd

from scouting.db import connect
from scouting.ingest import ingest
from scouting.sources.base import MatchData
from scouting.sources.statsbomb import EVENT_COLUMNS, PLAYER_COLUMNS, STINT_COLUMNS


class FakeSource:
    name = "fake"

    def fetch_matches(self, competition_id, season_id):
        return pd.DataFrame([{
            "match_id": 1, "competition_id": 2, "competition_name": "PL", "season_id": 27,
            "season_name": "2015/2016", "match_date": "2016-01-01", "home_team": "A",
            "away_team": "B", "home_score": 1, "away_score": 0}])

    def fetch_match_data(self, match_id):
        events = pd.DataFrame([{
            "event_idx": 1, "period": 1, "minute": 1, "second": 0, "type": "Pass",
            "sub_type": None, "outcome": None, "team": "A", "player_id": 10,
            "position": "Center Back", "role": "CB", "x": 30.0, "y": 40.0,
            "end_x": 60.0, "end_y": 40.0, "xg": None}], columns=EVENT_COLUMNS)
        stints = pd.DataFrame([
            {"player_id": 10, "team": "A", "position": "Center Back", "from_period": 1, "from_s": 0,
                 "to_period": None, "to_s": None},
            {"player_id": 11, "team": "A", "position": "Center Back", "from_period": 1, "from_s": 0,
                 "to_period": 1, "to_s": 0},  # unused sub: 0 minutes
        ], columns=STINT_COLUMNS)
        players = pd.DataFrame([{"player_id": 10, "player_name": "Ann", "player_nickname": None},
                                {"player_id": 11, "player_name": "Bo", "player_nickname": None}],
                               columns=PLAYER_COLUMNS)
        return MatchData(events, stints, players, {1: 2700, 2: 5400})


def test_ingest_loads_and_is_idempotent():
    con = connect(":memory:")
    assert ingest(con, FakeSource(), [(2, 27)]) == 1
    assert ingest(con, FakeSource(), [(2, 27)]) == 0
    assert con.execute("SELECT minutes FROM player_minutes").fetchall() == [(90.0,)]
    assert con.execute("SELECT count(*) FROM players").fetchone()[0] == 2
    assert con.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    assert con.execute("SELECT season_name FROM matches").fetchone()[0] == "2015/2016"
