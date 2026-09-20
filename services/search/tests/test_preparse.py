"""The weekday calendar resolver: dates a model could not work out, in code.

Every date below is a real 2026/2027 date. The full check against the live
page and three others is evals/inkclub_dates; these pin the rules.
"""

from datetime import date

from agent import preparse


def dated(text: str, today: date) -> list[str]:
    resolved, _ = preparse.resolve(text, today)
    return [line[:10] for line in resolved.splitlines() if line[:2] == "20"]


def test_the_weekday_picks_the_year():
    # Nothing on the page says 2026: GIO 2 luglio is a Thursday only in 2026
    # among the neighbouring years.
    page = "Luglio\nGIO 2club\ndalle 22:00\nTORNEO FOOTBALINO\n"
    resolved, unresolved = preparse.resolve(page, date(2026, 6, 30))
    assert unresolved == []
    assert "2026-07-02 (giovedì 2 luglio 2026) club" in resolved
    # Everything else stays exactly as printed.
    assert "dalle 22:00\nTORNEO FOOTBALINO" in resolved


def test_the_page_runs_into_the_next_month_without_saying_so():
    """Ink Club's live page: 'Luglio', then VEN 31 and SAB 1 — which is
    1 August, since 1 July 2026 was a Wednesday."""
    page = "Luglio\nVEN 24 club\nVEN 31Crotta\nSAB 1Crotta\nDOM 2Crotta\nDOM 30Crotta\n"
    assert dated(page, date(2026, 6, 30)) == [
        "2026-07-24",
        "2026-07-31",
        "2026-08-01",
        "2026-08-02",
        "2026-08-30",
    ]


def test_december_runs_into_next_year():
    page = "Dicembre\nGIO 31#pub\nVEN 1#club\nSAB 2#pub\n"
    assert dated(page, date(2026, 12, 20)) == ["2026-12-31", "2027-01-01", "2027-01-02"]


def test_an_entry_no_date_fits_is_left_as_printed():
    # 31 July 2026 is a Friday, and no neighbouring month or year makes a
    # Sunday of it: it is reported, and never forced onto a date.
    page = "Luglio\nGIO 2club\nDOM 31Crotta\n"
    resolved, unresolved = preparse.resolve(page, date(2026, 6, 30))
    assert unresolved == ["DOM 31Crotta"]
    assert "\nDOM 31Crotta" in resolved


def test_only_an_upper_case_weekday_opens_an_entry():
    # "Mar 10 persone" in a blurb is prose; "MAR 10" is an entry.
    page = "Marzo\nMAR 10 #pub\nMar 10 persone al tavolo\n"
    resolved, _ = preparse.resolve(page, date(2026, 3, 3))
    assert resolved.splitlines()[1].startswith("2026-03-10")
    assert "Mar 10 persone al tavolo" in resolved


def test_nothing_is_touched_before_a_month_heading():
    page = "GIO 2club\nLuglio\n"
    assert preparse.resolve(page, date(2026, 6, 30)) == (page.rstrip("\n"), [])
