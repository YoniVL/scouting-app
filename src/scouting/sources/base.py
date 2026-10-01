"""Contract every data source implements.

A source turns its raw data into three common-schema DataFrames per match.
Everything downstream (minutes, stats, percentiles) only sees these.

Event frame columns:
    event_idx, period, minute, second, type, sub_type, outcome, team,
    player_id, position, role, x, y, end_x, end_y, xg
Stint frame columns (one row per player position stint):
    player_id, team, position, from_period, from_s, to_period, to_s
    (`from_s`/`to_s` are match-clock seconds, `to_*` is None until the end)
Also `period_ends`: {period: end clock seconds} (final whistle per period).
Player frame columns:
    player_id, player_name, player_nickname
"""

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


@dataclass
class MatchData:
    events: pd.DataFrame
    stints: pd.DataFrame
    players: pd.DataFrame
    period_ends: dict[int, int]  # period -> end clock in seconds (final whistle)


class Source(Protocol):
    name: str

    def fetch_matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """Match metadata, with columns matching the `matches` table minus `source`."""
        ...

    def fetch_match_data(self, match_id: int) -> MatchData: ...
