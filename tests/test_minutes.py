from scouting.minutes import stint_seconds

ENDS = {1: 2750, 2: 5500}  # 45+5, then 45+10 -> match clock seconds


def test_full_match():
    assert stint_seconds(1, 0, None, None, ENDS) == 5500 - 2700 + 2750


def test_starter_subbed_off_in_second_half():
    assert stint_seconds(1, 0, 2, 3600, ENDS) == 2750 + (3600 - 2700)


def test_substitute_comes_on_at_60():
    assert stint_seconds(2, 3600, None, None, ENDS) == 5500 - 3600


def test_substitute_at_half_time():
    assert stint_seconds(2, 2700, 2, 4000, ENDS) == 4000 - 2700


def test_extra_time_counted_and_shootout_ignored():
    ends = {1: 2700, 2: 5400, 3: 6300, 4: 7200}
    assert stint_seconds(1, 0, None, None, ends) == 7200


def test_end_beyond_period_is_clamped():
    assert stint_seconds(1, 0, 1, 9999, ENDS) == 2750
