"""Central configuration: paths, thresholds and tunable definitions."""

from pathlib import Path

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "scouting.duckdb"
RAW_DIR = DATA_DIR / "raw"

# Minimum minutes in a role before a player counts in percentile pools
# and similarity candidates. Overridable on the CLI (--min-minutes).
MIN_MINUTES = 900

# Players above the minimum but below this get a softer "limited sample" note.
LIMITED_SAMPLE_MINUTES = 1500

# Preset "A": 2015/16 for Premier League (2), Ligue 1 (7), La Liga (11), Serie A (12).
# Entries are (competition_id, season_id) as in StatsBomb competitions.json.
PRESET_2015_16 = [(2, 27), (7, 27), (11, 27), (12, 27)]

# Progressive pass/carry (StatsBomb pitch is 120 x 80, goal centre at (120, 40)):
# must end entirely outside the own half, and reduce the distance to goal
# by at least max(PROGRESSIVE_MIN_UNITS, PROGRESSIVE_MIN_FRACTION * start distance).
PROGRESSIVE_MIN_FRACTION = 0.25
PROGRESSIVE_MIN_UNITS = 10.0
PROGRESSIVE_EXCLUDED_PASS_TYPES = {"Throw-in", "Corner", "Goal Kick", "Kick Off"}
