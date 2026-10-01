import numpy as np
import pandas as pd

from scouting.percentiles import PCT_COLS, compute_percentiles, percentile_of, sample_warning
from scouting.stats import P90_STATS


def make(rows):
    df = pd.DataFrame(rows, columns=["player_id", "role", "minutes", "v"])
    df["source"], df["season_name"] = "s", "2015/2016"
    for s in P90_STATS:
        df[s] = df["v"]
    return df


def test_percentile_of_midrank():
    assert percentile_of(np.array([1, 5, 9]), np.array([1, 2, 3, 4])).tolist() == [12.5, 100, 100]
    assert percentile_of(np.array([2.5]), np.array([])).tolist()[0] != 0  # NaN, not 0


def test_pool_excludes_low_minutes_but_ranks_them():
    df = make([(1, "CB", 2000, 1.0), (2, "CB", 2000, 2.0), (3, "CB", 2000, 3.0),
               (4, "CB", 100, 10.0)])  # below minimum: not in pool, still ranked
    out = compute_percentiles(df, min_minutes=900).set_index("player_id")
    assert out["pool_size"].iloc[0] == 3
    assert not out.loc[4, "eligible"]
    assert out.loc[4, PCT_COLS[0]] == 100
    assert out.loc[2, PCT_COLS[0]] == 50


def test_pools_are_per_role():
    df = make([(1, "CB", 2000, 1.0), (2, "ST", 2000, 99.0)])
    out = compute_percentiles(df, 900)
    assert out[PCT_COLS[0]].tolist() == [50, 50]


def test_sample_warning_levels():
    assert "Small sample" in sample_warning(300, 900)
    assert "Limited sample" in sample_warning(1200, 900)
    assert sample_warning(2500, 900) is None
