"""Percentiles within (season, role) pools of players with enough minutes."""

import numpy as np
import pandas as pd

from . import config
from .stats import P90_STATS

POOL_KEYS = ["season_name", "role"]
PCT_COLS = [f"{s}_pct" for s in P90_STATS]


def percentile_of(values: np.ndarray, pool: np.ndarray) -> np.ndarray:
    """Mid-rank percentile (0-100) of each value against `pool`; NaN if pool is empty."""
    if len(pool) == 0:
        return np.full(len(values), np.nan)
    pool = np.sort(pool)
    below = np.searchsorted(pool, values, side="left")
    through = np.searchsorted(pool, values, side="right")
    return 100 * (below + through) / 2 / len(pool)


def compute_percentiles(stats: pd.DataFrame, min_minutes: float = config.MIN_MINUTES) -> pd.DataFrame:
    """Add `eligible`, `pool_size` and one `<stat>_pct` column per per-90 stat.

    The pool is the eligible players of the same season and role; every player
    (also below the minimum) is ranked against that pool.
    """
    out = stats.copy()
    out["eligible"] = out["minutes"] >= min_minutes
    out["pool_size"] = out.groupby(POOL_KEYS)["eligible"].transform("sum").astype(int)
    for stat, col in zip(P90_STATS, PCT_COLS, strict=True):
        out[col] = np.nan
        for idx in out.groupby(POOL_KEYS).groups.values():
            grp = out.loc[idx]
            pool = grp.loc[grp["eligible"], stat].to_numpy()
            out.loc[idx, col] = percentile_of(grp[stat].to_numpy(), pool)
    return out


def sample_warning(minutes: float, min_minutes: float = config.MIN_MINUTES) -> str | None:
    """Warning text for small samples, else None."""
    if minutes < min_minutes:
        return (f"Small sample: only {minutes:.0f} minutes (< {min_minutes:.0f}). "
                "Percentiles are indicative at best.")
    if minutes < config.LIMITED_SAMPLE_MINUTES:
        return f"Limited sample: {minutes:.0f} minutes; treat with some caution."
    return None
