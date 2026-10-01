"""Find players by (accent- and case-insensitive) name."""

import unicodedata

import pandas as pd


def normalize(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", text if isinstance(text, str) else "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def find_players(players: pd.DataFrame, query: str) -> pd.DataFrame:
    """Rows of `players` (player_name, player_nickname) whose names contain all query words.

    An exact full-name or nickname match wins over partial matches.
    """
    words = normalize(query).split()
    names = players["player_name"].map(normalize)
    nicks = players["player_nickname"].map(normalize)
    exact = players[(names == " ".join(words)) | (nicks == " ".join(words))]
    if not exact.empty:
        return exact
    both = names + " " + nicks
    return players[both.map(lambda s: all(w in s for w in words))]
