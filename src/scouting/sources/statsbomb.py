"""StatsBomb Open Data source: cached download + mapping to the common schema.

Data: https://github.com/statsbomb/open-data (credit StatsBomb when sharing results).
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests

from .. import config
from ..roles import position_to_role
from .base import MatchData

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
NAME = "statsbomb"

EVENT_TYPES_KEPT = {"Pass", "Carry", "Shot", "Duel", "Interception", "Pressure"}


def clock_to_seconds(clock: str | None) -> float | None:
    """'45:30' -> 2730.0"""
    if not clock:
        return None
    m, s = clock.split(":")[:2]
    return int(m) * 60 + int(s)


class StatsBombSource:
    name = NAME

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = (cache_dir or config.RAW_DIR) / NAME
        self.session = requests.Session()

    def _get_json(self, rel_path: str):
        """Fetch a JSON file, caching it on disk. Retries with exponential backoff."""
        cached = self.cache_dir / rel_path
        if cached.exists():
            return json.loads(cached.read_text())
        for attempt in range(5):
            try:
                resp = self.session.get(f"{BASE_URL}/{rel_path}", timeout=60)
                resp.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(2**attempt)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(resp.content)
        return resp.json()

    def fetch_matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        return parse_matches(self._get_json(f"matches/{competition_id}/{season_id}.json"))

    def fetch_match_data(self, match_id: int) -> MatchData:
        events = self._get_json(f"events/{match_id}.json")
        lineups = self._get_json(f"lineups/{match_id}.json")
        return MatchData(
            parse_events(events), parse_stints(lineups), parse_players(lineups),
            parse_period_ends(events),
        )


def parse_matches(raw: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": m["match_id"],
            "competition_id": m["competition"]["competition_id"],
            "competition_name": m["competition"]["competition_name"],
            "season_id": m["season"]["season_id"],
            "season_name": m["season"]["season_name"],
            "match_date": m["match_date"],
            "home_team": m["home_team"]["home_team_name"],
            "away_team": m["away_team"]["away_team_name"],
            "home_score": m["home_score"],
            "away_score": m["away_score"],
        }
        for m in raw
    )


def _event_row(e: dict) -> dict:
    etype = e["type"]["name"]
    sub = outcome = end = xg = None
    if etype == "Pass":
        p = e["pass"]
        sub = p.get("type", {}).get("name")
        outcome = p.get("outcome", {}).get("name")  # absent == completed
        end = p.get("end_location")
    elif etype == "Carry":
        end = e["carry"]["end_location"]
    elif etype == "Shot":
        s = e["shot"]
        sub, outcome, xg = s.get("type", {}).get("name"), s["outcome"]["name"], s.get("statsbomb_xg")
    elif etype == "Duel":
        sub = e["duel"].get("type", {}).get("name")
        outcome = e["duel"].get("outcome", {}).get("name")
    loc = e.get("location") or [None, None]
    pos = e.get("position", {}).get("name")
    return {
        "event_idx": e["index"], "period": e["period"], "minute": e["minute"],
        "second": e["second"], "type": etype, "sub_type": sub, "outcome": outcome,
        "team": e["team"]["name"], "player_id": e["player"]["id"], "position": pos,
        "role": position_to_role(pos), "x": loc[0], "y": loc[1],
        "end_x": end[0] if end else None, "end_y": end[1] if end else None, "xg": xg,
    }


def parse_events(raw: list[dict]) -> pd.DataFrame:
    """Events of the kept types (those the stats need)."""
    rows = [_event_row(e) for e in raw if e["type"]["name"] in EVENT_TYPES_KEPT and "player" in e]
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def parse_period_ends(raw: list[dict]) -> dict[int, int]:
    """Period -> end clock in seconds, from 'Half End' events (shoot-out excluded)."""
    ends: dict[int, int] = {}
    for e in raw:
        if e["type"]["name"] == "Half End" and e["period"] <= 4:
            ends[e["period"]] = e["minute"] * 60 + e["second"]
    return ends


def parse_stints(lineups: list[dict]) -> pd.DataFrame:
    rows = []
    for team in lineups:
        for pl in team["lineup"]:
            for pos in pl["positions"]:
                rows.append(
                    {
                        "player_id": pl["player_id"], "team": team["team_name"],
                        "position": pos["position"], "from_period": pos["from_period"],
                        "from_s": clock_to_seconds(pos["from"]),
                        "to_period": pos["to_period"], "to_s": clock_to_seconds(pos["to"]),
                    }
                )
    return pd.DataFrame(rows, columns=STINT_COLUMNS)


def parse_players(lineups: list[dict]) -> pd.DataFrame:
    rows = [
        {"player_id": p["player_id"], "player_name": p["player_name"],
         "player_nickname": p.get("player_nickname")}
        for team in lineups
        for p in team["lineup"]
    ]
    return pd.DataFrame(rows, columns=PLAYER_COLUMNS)


EVENT_COLUMNS = [
    "event_idx", "period", "minute", "second", "type", "sub_type", "outcome", "team",
    "player_id", "position", "role", "x", "y", "end_x", "end_y", "xg",
]
STINT_COLUMNS = ["player_id", "team", "position", "from_period", "from_s", "to_period", "to_s"]
PLAYER_COLUMNS = ["player_id", "player_name", "player_nickname"]
