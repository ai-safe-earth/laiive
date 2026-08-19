"""Identity normalization — the MERGE keys that stop duplicate nodes."""

import re
import unicodedata


def norm(name: str) -> str:
    """lowercase, trimmed, diacritics stripped — the MERGE identity key."""
    s = unicodedata.normalize("NFD", name.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Spellings of one genre that the graph should not hold twice. Deliberately
# short: it exists for variants of a single style, not for taste judgements
# about which styles are really the same. Every entry here was either found in
# the graph ('electronica' beside 'electronic', 'rnb' beside 'r-b-pop-new-wave')
# or is a spelling a user is likely to type.
GENRE_ALIASES = {
    "electronica": "electronic",
    "electro": "electronic",
    "edm": "electronic",
    "r-b": "rnb",
    "r-and-b": "rnb",
    "rhythm-and-blues": "rnb",
    "regueton": "reggaeton",
    "reggeton": "reggaeton",
    "hiphop": "hip-hop",
    "hip-hop-rap": "hip-hop",
    "cantautor": "singer-songwriter",
    "songwriter": "singer-songwriter",
    "classical-music": "classical",
    "musica-clasica": "classical",
}

# Words extraction has emitted in the genre field that are not genres. A tag
# nobody can ever query for is worse than no tag: it satisfies the "has a
# genre" test while telling a reader nothing. Regional and language labels
# ('flamenco', 'punjabi') are NOT here — they are informative, even when they
# are more scene than style.
NON_GENRES = frozenset(
    {
        "various",
        "varios",
        "misc",
        "other",
        "otros",
        "unknown",
        "live",
        "music",
        "concert",
    }
)


def genre_slug(genre: str) -> str:
    """Normalize a genre name to its slug: 'Indie Rock' → 'indie-rock'.

    Aliases collapse to one spelling so the graph holds one node per genre;
    a word that is not a genre at all comes back empty, which every caller
    already treats as "no genre".
    """
    s = norm(genre)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if s in NON_GENRES:
        return ""
    return GENRE_ALIASES.get(s, s)


def genre_family(genre: str) -> list[str]:
    """Every stored spelling a query for this genre should reach.

    Canonicalising on write only helps rows written after it: 'electronica' is
    on two artists already and stays there, so the query has to ask for the
    whole family. Ordered for a stable Cypher parameter.
    """
    slug = genre_slug(genre)
    if not slug:
        return []
    variants = {slug} | {
        v for v, canonical in GENRE_ALIASES.items() if canonical == slug
    }
    return sorted(variants)
