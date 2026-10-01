"""Minutes played per stint, from lineup stints and the match's period lengths.

Clock convention: seconds on the match clock (period 2 starts at 2700, etc.).
Penalty shoot-outs (period 5) are not counted.
"""

import pandas as pd

PERIOD_START_S = {1: 0, 2: 2700, 3: 5400, 4: 6300}


def stint_seconds(from_period: int, from_s: float, to_period, to_s, ends: dict[int, int]) -> float:
    """Seconds played in one stint; `to_*` None means until the final whistle."""
    last = max(ends)
    to_period = last if pd.isna(to_period) else int(to_period)
    total = 0.0
    for p in range(int(from_period), to_period + 1):
        if p not in ends:
            continue
        start = from_s if p == from_period else PERIOD_START_S[p]
        end = to_s if (p == to_period and not pd.isna(to_s)) else ends[p]
        total += max(0.0, min(end, ends[p]) - start)
    return total


def add_minutes(stints: pd.DataFrame, ends: dict[int, int]) -> pd.DataFrame:
    """Return stints with a `minutes` column. `ends` maps period -> end clock seconds."""
    out = stints.copy()
    out["minutes"] = [
        stint_seconds(r.from_period, r.from_s, r.to_period, r.to_s, ends) / 60
        for r in out.itertuples()
    ]
    return out
