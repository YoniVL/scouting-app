import pandas as pd

from scouting.lookup import find_players, normalize
from scouting.percentiles import PCT_COLS
from scouting.similarity import similar_players


def row(pid, role, base, eligible=True):
    d = {"source": "s", "player_id": pid, "season_name": "2015/2016", "role": role,
         "eligible": eligible}
    d.update({c: v for c, v in zip(PCT_COLS, base, strict=True)})
    return d


def test_similar_ranks_by_shape_and_respects_role_and_eligibility():
    hi_lo = [90, 90, 90, 10, 10, 10, 10, 10, 10]
    rows = [
        row(1, "ST", hi_lo),                                   # target
        row(2, "ST", [85, 95, 80, 15, 5, 10, 20, 10, 5]),     # same shape
        row(3, "ST", [10, 10, 10, 90, 90, 90, 90, 90, 90]),   # opposite shape
        row(4, "ST", [60, 40, 55, 45, 50, 52, 48, 51, 49]),   # in-between
        row(5, "CB", hi_lo),                                   # other role
        row(6, "ST", hi_lo, eligible=False),                   # below minimum
    ]
    pct = pd.DataFrame(rows)
    res = similar_players(pct, pct.iloc[0], top=10)
    assert list(res["player_id"]) == [2, 4, 3]
    assert res["similarity"].iloc[0] > 0.9
    assert res["similarity"].iloc[-1] < 0


def test_find_players_accent_insensitive_and_exact_wins():
    players = pd.DataFrame({
        "player_name": ["Sergio Agüero del Castillo", "Sergio Busquets Burgos", "Ana"],
        "player_nickname": ["Sergio Agüero", None, None]})
    assert normalize("Agüero") == "aguero"
    assert len(find_players(players, "aguero")) == 1
    assert len(find_players(players, "sergio")) == 2
    assert len(find_players(players, "Sergio Agüero")) == 1  # exact nickname beats partial
