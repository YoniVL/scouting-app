"""Similarity search: standardised percentiles + cosine similarity, within one role."""

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from .percentiles import PCT_COLS


def similar_players(pct: pd.DataFrame, target: pd.Series,
                    top: int | None = 10) -> pd.DataFrame:
    """Most similar eligible players of the target's role (target itself excluded).

    `pct` must come from `compute_percentiles`. Features are the percentile columns,
    z-scored over the eligible pool of that role, then compared by cosine similarity.
    `top=None` returns all candidates (so callers can filter before cutting).
    """
    pool = pct[(pct["role"] == target["role"]) & pct["eligible"]]
    pool = pool[~((pool["source"] == target["source"])
                  & (pool["player_id"] == target["player_id"])
                  & (pool["season_name"] == target["season_name"]))]
    if pool.empty:
        return pool.assign(similarity=[])
    scaler = StandardScaler().fit(pool[PCT_COLS])
    sims = cosine_similarity(scaler.transform(target[PCT_COLS].to_frame().T.astype(float)),
                             scaler.transform(pool[PCT_COLS]))[0]
    return pool.assign(similarity=sims).sort_values("similarity", ascending=False).head(top or len(pool))
