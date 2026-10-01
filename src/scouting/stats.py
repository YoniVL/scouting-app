"""Per-player, per-season, per-role aggregates and per-90 rates."""

import numpy as np
import pandas as pd

from . import config
from .roles import ROLES

# Count columns and their per-90 counterparts, in display order.
COUNT_STATS = [
    "passes", "progressive_passes", "carries", "progressive_carries",
    "shots", "npxg", "tackles", "interceptions", "pressures",
]
P90_STATS = [f"{s}_p90" for s in COUNT_STATS]

GOAL_X, GOAL_Y = 120.0, 40.0
KEYS = ["source", "player_id", "season_name", "role"]


def _dist_to_goal(x, y):
    return np.hypot(GOAL_X - x, GOAL_Y - y)


def progressive_mask(df: pd.DataFrame) -> pd.Series:
    """True where a move (start x/y -> end_x/end_y) is progressive.

    Not entirely within the own half, and at least
    max(PROGRESSIVE_MIN_UNITS, PROGRESSIVE_MIN_FRACTION * start distance) closer to goal.
    """
    start = _dist_to_goal(df["x"], df["y"])
    end = _dist_to_goal(df["end_x"], df["end_y"])
    needed = np.maximum(config.PROGRESSIVE_MIN_UNITS, config.PROGRESSIVE_MIN_FRACTION * start)
    own_half = (df["x"] < 60) & (df["end_x"] < 60)
    return (start - end >= needed) & ~own_half


def flag_events(ev: pd.DataFrame) -> pd.DataFrame:
    """Add one 0/1 (or xG) column per COUNT_STATS entry."""
    t, sub = ev["type"], ev["sub_type"]
    prog = progressive_mask(ev)
    completed = ev["outcome"].isna()
    open_play_pass = ~sub.isin(config.PROGRESSIVE_EXCLUDED_PASS_TYPES)
    non_pen_shot = (t == "Shot") & (sub != "Penalty")
    flags = {
        "passes": t == "Pass",
        "progressive_passes": (t == "Pass") & completed & open_play_pass & prog,
        "carries": t == "Carry",
        "progressive_carries": (t == "Carry") & prog,
        "shots": non_pen_shot,
        "tackles": (t == "Duel") & (sub == "Tackle"),
        "interceptions": t == "Interception",
        "pressures": t == "Pressure",
    }
    out = ev[KEYS].copy()
    for name, mask in flags.items():
        out[name] = mask.astype(float)
    out["npxg"] = ev["xg"].where(non_pen_shot, 0.0).fillna(0.0)
    return out


def event_counts(ev: pd.DataFrame) -> pd.DataFrame:
    """Summed counts per (source, player, season, role) from raw event rows."""
    return flag_events(ev).groupby(KEYS, as_index=False)[COUNT_STATS].sum()


def add_per90(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for stat in COUNT_STATS:
        out[f"{stat}_p90"] = out[stat] / out["minutes"] * 90
    return out


def combine(minutes: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    """Minutes rows left-joined with event counts (missing counts = 0), plus per-90 rates."""
    df = minutes.merge(counts, on=KEYS, how="left")
    df[COUNT_STATS] = df[COUNT_STATS].fillna(0.0)
    return add_per90(df)


_ROLE_LIST = ", ".join(f"'{r}'" for r in ROLES)

MINUTES_SQL = f"""
SELECT pm.source, pm.player_id, p.player_name, m.season_name, pm.role,
       string_agg(DISTINCT pm.team, ', ') AS teams,
       string_agg(DISTINCT m.competition_name, ', ') AS competitions,
       count(DISTINCT pm.match_id)::INTEGER AS matches, sum(pm.minutes) AS minutes
FROM player_minutes pm
JOIN matches m USING (source, match_id)
JOIN players p USING (source, player_id)
WHERE pm.role IN ({_ROLE_LIST})
GROUP BY pm.source, pm.player_id, p.player_name, m.season_name, pm.role
"""

EVENTS_SQL = f"""
SELECT e.source, e.player_id, m.season_name, e.role, e.type, e.sub_type, e.outcome,
       e.x, e.y, e.end_x, e.end_y, e.xg
FROM events e JOIN matches m USING (source, match_id)
WHERE e.role IN ({_ROLE_LIST})
"""


def build_player_season_stats(con) -> int:
    """Rebuild the `player_season_stats` table from raw tables. Returns row count."""
    minutes = con.execute(MINUTES_SQL).df()
    counts = event_counts(con.execute(EVENTS_SQL).df())
    stats = combine(minutes, counts)
    con.execute("DELETE FROM player_season_stats")
    con.register("_stats", stats)
    cols = ", ".join(stats.columns)
    con.execute(f"INSERT INTO player_season_stats ({cols}) SELECT {cols} FROM _stats")
    con.unregister("_stats")
    return len(stats)
