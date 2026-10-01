from scouting.sources.statsbomb import (
    clock_to_seconds, parse_events, parse_period_ends, parse_stints,
)


def ev(typ, idx=1, **extra):
    base = {"index": idx, "period": 1, "minute": 10, "second": 5, "type": {"name": typ},
            "team": {"name": "A"}, "player": {"id": 7}, "position": {"name": "Left Back"},
            "location": [50.0, 20.0]}
    return base | extra


def test_clock_to_seconds():
    assert clock_to_seconds("45:30") == 2730
    assert clock_to_seconds(None) is None


def test_parse_events_pass_shot_and_filtering():
    raw = [
        ev("Pass", 1, **{"pass": {"end_location": [70, 20], "type": {"name": "Corner"}}}),
        ev("Shot", 2, shot={"statsbomb_xg": 0.3, "outcome": {"name": "Goal"},
                            "type": {"name": "Penalty"}}),
        ev("Ball Receipt*", 3),
        ev("Duel", 4, duel={"type": {"name": "Tackle"}, "outcome": {"name": "Won"}}),
    ]
    df = parse_events(raw)
    assert list(df["type"]) == ["Pass", "Shot", "Duel"]
    assert df.loc[0, "end_x"] == 70 and df.loc[0, "sub_type"] == "Corner"
    assert df.loc[1, "xg"] == 0.3 and df.loc[1, "sub_type"] == "Penalty"
    assert df.loc[0, "role"] == "FB"


def test_period_ends_ignore_shootout():
    raw = [
        {"type": {"name": "Half End"}, "period": 1, "minute": 46, "second": 7},
        {"type": {"name": "Half End"}, "period": 2, "minute": 94, "second": 38},
        {"type": {"name": "Half End"}, "period": 5, "minute": 120, "second": 0},
    ]
    assert parse_period_ends(raw) == {1: 2767, 2: 5678}


def test_parse_stints():
    lineups = [{"team_name": "A", "lineup": [{"player_id": 1, "positions": [
        {"position": "Goalkeeper", "from": "00:00", "to": "60:00", "from_period": 1,
         "to_period": 2}]}]}]
    row = parse_stints(lineups).iloc[0]
    assert row["to_s"] == 3600 and row["to_period"] == 2 and row["team"] == "A"
