"""Identity normalization — the MERGE keys that stop duplicate nodes."""

import re
import unicodedata


def norm(name: str) -> str:
    """lowercase, trimmed, diacritics stripped — the MERGE identity key."""
    s = unicodedata.normalize("NFD", name.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def genre_slug(genre: str) -> str:
    """Normalize a genre name to its slug: 'Indie Rock' → 'indie-rock'."""
    s = norm(genre)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
