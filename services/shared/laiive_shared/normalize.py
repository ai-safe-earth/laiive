"""Identity normalization — the MERGE keys that stop duplicate nodes."""

import re
import unicodedata
from urllib.parse import urlparse


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


def source_domain(url: str) -> str:
    """The host a discovered listing came from, as a grouping key.

    Lowercased and stripped of "www." so one site is one key: a sweep sees
    both www.ecodibergamo.it and ecodibergamo.it, and counting them as two
    sources would halve the evidence for each and let a good site sit below a
    promotion threshold forever.

    The port is kept — a host answering on a non-default port is a different
    service — and an unparseable URL yields "" rather than raising, because a
    missing domain must never fail a write.
    """
    if not url:
        return ""
    try:
        host = urlparse(url.strip()).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


# "Ponteranica, BG" and "Ponteranica (BG)" are how an Italian address names a
# comune plus its province. Both are already in the graph as their own City,
# which is the failure that matters: City identity is (name_norm, country_code),
# so the suffixed spelling is a second city nobody can search for, holding
# events the unsuffixed one will never return.
#
# Deliberately narrow — a two-letter code, uppercase, at the very end, after a
# comma or in brackets. It does mean "Austin, TX" becomes "Austin"; that is the
# right shape for this graph (the country code carries the disambiguation) but
# would need real admin-level handling before a US launch, where two states can
# hold the same city name.
_PROVINCE_SUFFIX = re.compile(r"\s*[,(]\s*([A-Z]{2})\s*\)?\s*$")


def clean_city_name(city: str) -> str:
    """Drop a trailing province/state code so one town is one City node."""
    if not city:
        return ""
    return _PROVINCE_SUFFIX.sub("", city.strip()).strip() or city.strip()


def canonical_city_name(display_name: str) -> str:
    """The local name of a place, from a geocoder's display name.

    An English page writes Turin, an Italian one Torino, and City identity is
    (name_norm, country_code) — so one Torino sweep produced eight candidates
    saying Torino and seven saying Turin, which is two cities and a search that
    returns half its events. The same split waits in Munich/Munchen and
    Florence/Firenze for any sweep that reaches them.

    Nominatim answers in the local language, so its first component is the
    endonym whichever spelling was asked for. Returns "" when there is nothing
    usable, and the caller keeps what it had.
    """
    first = (display_name or "").split(",")[0].strip()
    # A house number or postcode as the leading component means the answer was
    # an address, not a place, and renaming a city after it would be worse than
    # the split it is fixing.
    return "" if first.isdigit() else first
