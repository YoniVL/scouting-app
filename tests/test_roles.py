from scouting.roles import ROLES, position_to_role


def test_known_positions():
    assert position_to_role("Right Center Back") == "CB"
    assert position_to_role("Left Wing Back") == "FB"
    assert position_to_role("Center Defensive Midfield") == "CM"
    assert position_to_role("Right Midfield") == "W"
    assert position_to_role("Secondary Striker") == "ST"
    assert position_to_role("Goalkeeper") == "GK"


def test_unknown_and_none():
    assert position_to_role("Nonsense") is None
    assert position_to_role(None) is None
    assert "GK" not in ROLES
