"""Resolve a weekday-and-day club calendar into explicit dates, in code.

A candidate for agent/, kept here until the evaluation beside it says whether
it earns a place there. It rewrites text and decides nothing else: which
entries are live music, what they are called and who plays stay the model's.

The format is Ink Club's: a month name alone on a line, then entries that
open with a weekday and a day ("GIO 5#pub", "SAB 25Ninfea"), running on into
the next month with no new heading. Nothing on the page gives a year.

The printed weekday is what makes this solvable without guessing. A day of a
month falls on a given weekday in exactly one of any three neighbouring
years, so the weekday picks the year; and when the page slips into the next
month unannounced, the weekday stops fitting the old month and fits the new
one. An entry that fits nothing is left exactly as printed, for the model and
the reviewer to see, rather than being forced onto a date.
"""

import re
from datetime import date

MONTHS = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)
WEEKDAYS = {"LUN": 0, "MAR": 1, "MER": 2, "GIO": 3, "VEN": 4, "SAB": 5, "DOM": 6}
WEEKDAY_NAMES = (
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
)

# A month alone on its line, with or without a year. Case-blind: headings are
# "Marzo". An entry is upper case only, so "Mar 10 persone" in a blurb is not
# one — and MAR the Tuesday never collides with Marzo the heading.
HEADING = re.compile(
    r"^\s*(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?\s*$", re.IGNORECASE
)
ENTRY = re.compile(r"^\s*(LUN|MAR|MER|GIO|VEN|SAB|DOM)\s+(\d{1,2})(?!\d)\s*(.*)$")


def _on(year: int, month: int, day: int, weekday: int) -> date | None:
    """That date, if it exists and falls on that weekday."""
    try:
        found = date(year, month, day)
    except ValueError:  # 31 giugno
        return None
    return found if found.weekday() == weekday else None


def resolve(text: str, today: date) -> tuple[str, list[str]]:
    """(the text with every entry line dated, the entry lines that fit no date)."""
    month: int | None = None
    year: int | None = None
    last_day = 0
    out: list[str] = []
    unresolved: list[str] = []

    for line in text.splitlines():
        if heading := HEADING.match(line):
            month = MONTHS.index(heading[1].lower()) + 1
            year = int(heading[2]) if heading[2] else None
            last_day = 0
            out.append(line)
            continue
        entry = ENTRY.match(line)
        if entry is None or month is None:
            out.append(line)
            continue

        weekday, day, rest = WEEKDAYS[entry[1]], int(entry[2]), entry[3]
        following = month % 12 + 1
        # A day number that drops is the page's only sign of a new month, so
        # that month is tried first. It matters after a 28-day February, the
        # one case where a day fits both months on the same weekday.
        order = (following, month) if day < last_day else (month, following)
        # No year known yet: the nearest years, this one first. Once an entry
        # has fixed it the page stays in it, give or take a new year.
        years = (
            (year, year + 1) if year else (today.year, today.year + 1, today.year - 1)
        )

        found = None
        for candidate_month in order:
            for candidate_year in years:
                # December running into January is next year's January.
                wrapped = candidate_month < month and candidate_month == following
                found = _on(
                    candidate_year + (1 if wrapped and year else 0),
                    candidate_month,
                    day,
                    weekday,
                )
                if found:
                    break
            if found:
                break

        if found is None:
            unresolved.append(line.strip())
            out.append(line)
            continue
        month, year, last_day = found.month, found.year, day
        label = f"{WEEKDAY_NAMES[weekday]} {day} {MONTHS[found.month - 1]} {found.year}"
        out.append(f"{found.isoformat()} ({label}) {rest}".rstrip())

    return "\n".join(out), unresolved
