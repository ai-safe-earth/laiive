from dataclasses import dataclass
from datetime import date

import pytest
from laiive_shared.cards import EventDraft
from laiive_shared.checks import (
    check_draft,
    city_name_of,
    claimed_weekday,
    past_date_doubt,
    tidy_case,
    weekday_doubt,
)

# 2026-09-15 is a Tuesday. Every date below is checked against a real calendar,
# because a test that agrees with the bug proves nothing.
TUESDAY = "2026-09-15T21:00:00"
TODAY = date(2026, 9, 1)


class FakeGeocoder:
    """Answers one question, offline. `answers` maps a query to a display_name."""

    def __init__(self, answers: dict[str, str] | None = None, raises: bool = False):
        self.answers = answers or {}
        self.raises = raises
        self.asked: list[str] = []

    def geocode(self, query: str):
        self.asked.append(query)
        if self.raises:
            raise RuntimeError("nominatim is down")
        label = self.answers.get(query.strip().lower())
        if label is None:
            return None

        @dataclass(frozen=True)
        class _Hit:
            display_name: str

        return _Hit(display_name=label)


# ── the weekday, which is the whole point of the layer ───────────────────────


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("Wednesday 15 September", 2),
        ("miércoles 15 de septiembre", 2),  # accents survive norm()
        ("Dimecres 15", 2),
        ("mercoledì 15 settembre", 2),
        ("sábado", 5),
        ("15 September", None),  # no weekday named, nothing to contradict
        ("", None),
    ],
)
def test_claimed_weekday_reads_four_languages(phrase, expected):
    assert claimed_weekday(phrase) == expected


def test_weekday_that_contradicts_the_date_is_a_doubt():
    doubt = weekday_doubt(TUESDAY, "Wednesday 15 September")
    assert doubt is not None
    assert doubt.field == "start_at"
    # It must name both readings; the promoter picks, we never guess.
    assert "Wednesday" in doubt.question and "Tuesday" in doubt.question
    assert "15 September 2026" in doubt.question


def test_weekday_that_agrees_is_silent():
    assert weekday_doubt(TUESDAY, "Tuesday 15 September") is None


def test_no_weekday_claimed_is_silent():
    assert weekday_doubt(TUESDAY, "15 September") is None


def test_unparseable_date_is_not_a_weekday_doubt():
    # missing_required and the writer own that failure; two owners means two
    # different messages for one problem.
    assert weekday_doubt("next tuesday-ish", "Wednesday") is None


# ── dates already gone ───────────────────────────────────────────────────────


def test_past_date_is_a_doubt():
    doubt = past_date_doubt("2025-09-15T21:00:00", TODAY)
    assert doubt is not None and doubt.field == "start_at"


def test_today_is_not_past():
    assert past_date_doubt("2026-09-01T21:00:00", TODAY) is None


# ── capitalisation, and what must not be touched ─────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        ("sala apolo", "Sala Apolo"),  # the one shape that is nearly always a slip
        ("la sala de al lado", "La Sala De Al Lado"),
        ("Sala Apolo", None),  # already fine
        ("SALA APOLO", None),  # all caps may be the name shouting; leave it
        ("MF DOOM", None),  # …because this is spelled exactly that way
        ("ANOHNI", None),
        ("iamamiwhoami", None),  # one lowercase word: real name or typo, unknowable
        ("girl in red", "Girl In Red"),  # multi-word loses that argument, and the
        ("tUnE-yArDs", None),  # form is where it gets overruled
        ("", None),
        ("123", None),
    ],
)
def test_tidy_case_only_fixes_multiword_lowercase(value, expected):
    assert tidy_case(value) == expected


def test_tidy_case_leaves_a_single_lowercase_word_alone():
    # "apolo" is as likely to be a band's own styling as a typo, and there is
    # no way to tell them apart here — so it is left for the form.
    assert tidy_case("apolo") is None


# ── the city, verified against a gazetteer ───────────────────────────────────


def test_city_name_of_takes_the_place_not_the_whole_label():
    assert city_name_of("Barcelona, Barcelonès, Catalunya, España") == "Barcelona"


def test_misspelled_case_city_is_corrected_from_the_map():
    draft = EventDraft(city="barcelona", start_at=TUESDAY)
    geo = FakeGeocoder({"barcelona": "Barcelona, Barcelonès, Catalunya, España"})
    corrections, doubts = check_draft(draft, geocoder=geo, today=TODAY)
    assert draft.city == "Barcelona"
    assert [c.field for c in corrections] == ["city"]
    assert not doubts


def test_unknown_city_is_a_doubt_not_a_correction():
    draft = EventDraft(city="Lanpetozia", start_at=TUESDAY)
    corrections, doubts = check_draft(draft, geocoder=FakeGeocoder(), today=TODAY)
    assert draft.city == "Lanpetozia"  # never silently replaced
    assert [d.field for d in doubts] == ["city"]
    assert not corrections


def test_a_different_place_answering_is_asked_never_swapped():
    # "Santiago" is four countries. Rewriting it would publish the event in the
    # wrong hemisphere without anyone being told.
    draft = EventDraft(city="Santiago", start_at=TUESDAY)
    geo = FakeGeocoder({"santiago": "Santiago de Compostela, Galicia, España"})
    _, doubts = check_draft(draft, geocoder=geo, today=TODAY)
    assert draft.city == "Santiago"
    assert [d.field for d in doubts] == ["city"]


def test_a_geocoder_outage_degrades_to_no_city_check():
    draft = EventDraft(city="Barcelona", start_at=TUESDAY)
    corrections, doubts = check_draft(
        draft, geocoder=FakeGeocoder(raises=True), today=TODAY
    )
    # An outage must not invent a doubt the promoter cannot answer either.
    assert draft.city == "Barcelona"
    assert not corrections
    assert [d.field for d in doubts] == ["city"]


def test_no_geocoder_skips_the_city_entirely():
    draft = EventDraft(city="barcelona", start_at=TUESDAY)
    corrections, doubts = check_draft(draft, geocoder=None, today=TODAY)
    assert draft.city == "barcelona"
    assert not corrections and not doubts


# ── the whole layer over one draft ───────────────────────────────────────────


def test_the_graph_spelling_of_a_venue_wins():
    draft = EventDraft(venue="sala apolo", start_at=TUESDAY)
    corrections, _ = check_draft(draft, known_venue="Sala Apolo [2]", today=TODAY)
    assert draft.venue == "Sala Apolo [2]"
    assert corrections[0].why == "the name this venue already goes by"


def test_artists_are_never_recased():
    # No authority backs a guess at an artist's spelling, and renaming somebody's
    # act is a worse failure than a lowercase name the promoter fixes on the form.
    draft = EventDraft(artists=["ana beck quartet", "MF DOOM"], start_at=TUESDAY)
    corrections, _ = check_draft(draft, today=TODAY)
    assert draft.artists == ["ana beck quartet", "MF DOOM"]
    assert not [c for c in corrections if c.field == "artists"]


def test_a_clean_draft_produces_nothing():
    draft = EventDraft(
        name="Jazz Night",
        artists=["Ana Beck Quartet"],
        venue="Sala Apolo",
        city="Barcelona",
        start_at=TUESDAY,
    )
    geo = FakeGeocoder({"barcelona": "Barcelona, Catalunya, España"})
    corrections, doubts = check_draft(draft, geocoder=geo, today=TODAY)
    assert not corrections and not doubts
