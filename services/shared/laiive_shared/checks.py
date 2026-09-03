"""The correction layer: what a draft gets wrong that nobody noticed.

`missing_required` answers "what is absent". This answers the other half —
what is *present and wrong* — and it splits the answer in two, because the two
halves want opposite treatment:

  - **Corrections** are applied to the draft. The promoter sees them already
    filled in on the review form and can overrule any of them there, which is
    why writing them straight onto the draft is safe: the form is the
    validation step, not a confirmation dialog nobody reads.
  - **Doubts** are questions only the promoter can settle. They ride back into
    the chat next to the missing fields and get asked in the same breath.

Nothing here calls a model. A geocoder is injected rather than imported so the
tests stay offline, the same way `write_event` takes one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .normalize import norm

# Every weekday name the four supported UI languages can produce, keyed to
# Python's Monday=0. Matched through `norm`, so accents and case are already
# gone by the time a key is looked up - "Miércoles" and "miercoles" are one.
_WEEKDAYS: dict[str, int] = {}
for _index, _names in enumerate(
    [
        ("monday", "lunes", "lunedi", "dilluns", "mon", "lun"),
        ("tuesday", "martes", "martedi", "dimarts", "tue", "mar"),
        ("wednesday", "miercoles", "mercoledi", "dimecres", "wed", "mie", "mier"),
        ("thursday", "jueves", "giovedi", "dijous", "thu", "jue"),
        ("friday", "viernes", "venerdi", "divendres", "fri", "vie"),
        ("saturday", "sabado", "sabato", "dissabte", "sat", "sab"),
        ("sunday", "domingo", "domenica", "diumenge", "sun", "dom"),
    ]
):
    for _name in _names:
        _WEEKDAYS[_name] = _index

# English is what the promoter is shown back, because the reply is written by a
# model that is already told which language to answer in - it translates the
# question, and a doubt phrased in two languages at once would not survive that.
_WEEKDAY_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True)
class Correction:
    """A value this layer changed, and what it was before."""

    field: str
    before: str
    after: str
    why: str


@dataclass(frozen=True)
class Doubt:
    """Something only the promoter can settle. `question` is asked verbatim."""

    field: str
    question: str


def claimed_weekday(phrase: str) -> int | None:
    """The weekday a date phrase names, if it names one.

    Reads the phrase the promoter actually wrote ("Wednesday 15 September"),
    not the parsed date - the whole point is to catch the two disagreeing, and
    once the extraction has resolved a date the disagreement is gone.
    """
    if not phrase:
        return None
    for token in norm(phrase).replace(",", " ").replace(".", " ").split():
        if token in _WEEKDAYS:
            return _WEEKDAYS[token]
    return None


def weekday_doubt(start_at: str, phrase: str) -> Doubt | None:
    """A weekday that contradicts the date it was written next to.

    "Wednesday 15 September" when the 15th is a Tuesday is the single most
    common thing wrong with a flyer, and it is invisible downstream: the
    extraction resolves a date and silently drops the weekday, so the event
    publishes on a day the promoter never meant. Neither half can be trusted
    over the other - a promoter who typed the wrong number and one who typed
    the wrong day look identical here - so this asks instead of guessing.
    """
    claimed = claimed_weekday(phrase)
    if claimed is None:
        return None
    try:
        actual = datetime.fromisoformat(start_at).date()
    except (TypeError, ValueError):
        return None
    if actual.weekday() == claimed:
        return None
    return Doubt(
        field="start_at",
        question=(
            f"the flyer says {_WEEKDAY_EN[claimed]} but {human_date(actual)} is a "
            f"{_WEEKDAY_EN[actual.weekday()]} — which one is right, the day or "
            f"the date?"
        ),
    )


def human_date(when: date) -> str:
    """ "15 September 2026". Built by hand rather than with `%-d`, which is a
    glibc extension Windows raises on."""
    return f"{when.day} {when:%B} {when.year}"


def past_date_doubt(start_at: str, today: date | None = None) -> Doubt | None:
    """A date already gone - nearly always a mistyped year on a flyer reused
    from last season. Asked rather than corrected: a promoter genuinely
    archiving an old night is rare but real, and guessing the year for them
    would publish a different event than the one they described."""
    try:
        when = datetime.fromisoformat(start_at).date()
    except (TypeError, ValueError):
        return None
    if when >= (today or date.today()):
        return None
    return Doubt(
        field="start_at",
        question=(
            f"{when.isoformat()} has already passed — did you mean a later date?"
        ),
    )


def tidy_case(value: str) -> str | None:
    """Capitalise a multi-word, all-lowercase value. Nothing else.

    This is as far as case can be fixed without an authority to check against,
    and the boundary is not timidity - every wider rule mangles real names:

      - ALL CAPS is not a mistake. "MF DOOM" and "ANOHNI" are spelled that way,
        and a flyer shouting its venue looks identical to a band that means it.
      - A single lowercase word is not a mistake either. "iamamiwhoami" and
        "girl in red" are correct; so is a promoter's typo. Nothing here can
        tell those apart, and guessing wrong renames somebody's act.
      - Mixed case is a statement. "tUnE-yArDs" is the name.

    Two or more words, none of them carrying any capital, is the one shape that
    is almost always careless typing rather than a decision. Even that is only
    ever *proposed*: it lands on the review form, where the promoter overrules
    it in one keystroke.

    Where a real authority exists - the gazetteer for a city, the graph for a
    venue already in it - that authority is used instead of this.
    """
    stripped = (value or "").strip()
    if not stripped or not any(c.isalpha() for c in stripped):
        return None
    if stripped != stripped.lower() or len(stripped.split()) < 2:
        return None
    return " ".join(w[:1].upper() + w[1:] for w in stripped.split())


def city_name_of(display_name: str) -> str:
    """The place itself out of a geocoder's full label.

    Nominatim answers "Barcelona, Barcelonès, Barcelona, Catalunya, España";
    the first component is the name the promoter meant.
    """
    return (display_name or "").split(",")[0].strip()


def check_draft(
    draft,
    *,
    geocoder=None,
    known_venue: str | None = None,
    today: date | None = None,
) -> tuple[list[Correction], list[Doubt]]:
    """Correct what can be corrected, ask about what cannot.

    Mutates `draft` in place with the corrections, because the draft *is* what
    the review form renders - a correction the promoter never sees is a silent
    edit, and one they see but cannot overrule is worse.

    `geocoder` is injected: it is the city verifier, and passing None (tests,
    or a turn that must not touch the network) simply skips the city checks
    rather than failing them, so a geocoder outage degrades to today's
    behaviour instead of blocking every submission.

    `known_venue` is the graph's own spelling of the venue when the caller
    already looked it up. Venues fork on spelling, so adopting the existing one
    is worth more here than anywhere else.
    """
    corrections: list[Correction] = []
    doubts: list[Doubt] = []

    def correct(field: str, after: str, why: str) -> None:
        before = getattr(draft, field, None) or ""
        if after and after != before:
            setattr(draft, field, after)
            corrections.append(Correction(field, before, after, why))

    # ── the date the promoter wrote, against the date that was parsed ────────
    if draft.start_at:
        # The claim is what the text said in words; extraction keeps it beside
        # the resolved timestamp precisely so these two can be compared.
        claim = getattr(draft, "start_at_claim", "") or ""
        conflict = weekday_doubt(draft.start_at, claim)
        if conflict:
            doubts.append(conflict)
        else:
            stale = past_date_doubt(draft.start_at, today)
            if stale:
                doubts.append(stale)

    # ── the city, against a real gazetteer ───────────────────────────────────
    if draft.city and geocoder is not None:
        try:
            hit = geocoder.geocode(draft.city)
        except Exception:
            hit = None  # an outage must not block a submission
        if hit is None:
            doubts.append(
                Doubt(
                    field="city",
                    question=(
                        f"I could not find a town called “{draft.city}” — "
                        f"which city is it in?"
                    ),
                )
            )
        else:
            canonical = city_name_of(hit.display_name)
            if canonical and norm(canonical) == norm(draft.city):
                # Same place, different spelling or case: take the gazetteer's.
                correct("city", canonical, "spelling from the map")
            elif canonical:
                # A different place answered. That is a real ambiguity - "Santiago"
                # is four countries - so it is asked, not silently swapped.
                doubts.append(
                    Doubt(
                        field="city",
                        question=(
                            f"by “{draft.city}” did you mean " f"{hit.display_name}?"
                        ),
                    )
                )

    # ── venue: prefer the spelling the graph already uses ────────────────────
    if known_venue:
        correct("venue", known_venue, "the name this venue already goes by")
    elif draft.venue:
        tidied = tidy_case(draft.venue)
        if tidied:
            correct("venue", tidied, "capitalisation")

    # Artists and the event title are deliberately left alone. Nothing here can
    # distinguish a typo from a name that is spelled that way on purpose, and
    # renaming somebody's act is a worse failure than a lowercase title the
    # promoter fixes on the form in one keystroke.

    return corrections, doubts
