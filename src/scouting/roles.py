"""Map detailed positions onto coarse role groups: GK, CB, FB, CM, AM, W, ST."""

ROLES = ["CB", "FB", "CM", "AM", "W", "ST"]  # GK is tracked but excluded from stats

POSITION_TO_ROLE = {
    "Goalkeeper": "GK",
    "Center Back": "CB", "Left Center Back": "CB", "Right Center Back": "CB",
    "Left Back": "FB", "Right Back": "FB", "Left Wing Back": "FB", "Right Wing Back": "FB",
    "Center Defensive Midfield": "CM", "Left Defensive Midfield": "CM",
    "Right Defensive Midfield": "CM", "Center Midfield": "CM",
    "Left Center Midfield": "CM", "Right Center Midfield": "CM",
    "Center Attacking Midfield": "AM", "Left Attacking Midfield": "AM",
    "Right Attacking Midfield": "AM",
    "Left Midfield": "W", "Right Midfield": "W", "Left Wing": "W", "Right Wing": "W",
    "Center Forward": "ST", "Left Center Forward": "ST", "Right Center Forward": "ST",
    "Secondary Striker": "ST",
}


def position_to_role(position: str | None) -> str | None:
    """Role group for a position name, or None if unknown."""
    return POSITION_TO_ROLE.get(position) if position else None
