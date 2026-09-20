"""Can the extractor date Ink Club's calendar, and does resolving the dates in
code first change that?

Run from services/search:
    PYTHONPATH=. uv run --no-sync python evals/inkclub_dates/run_eval.py

36 extractions, about a hundred small gpt-4o-mini calls (a few cents); no
Tavily, no graph, no store. Writes results.csv for a person to judge and
summary.md for the headline. README.md says what the columns mean.
"""

import csv
import json
import pathlib
import re
from datetime import date
from unittest.mock import patch

from agent import extraction, preparse

HERE = pathlib.Path(__file__).parent

URL = "https://www.inkclub.bergamo.it/calendario"

# Each page is read on three days, because the failure depends on the day: a
# programme that has just gone up, one half over, and one the club never took
# down — which is how the live page was found on 2026-09-19.
SCENARIOS = {
    "2026-03": {
        "fresh": date(2026, 3, 3),
        "mid": date(2026, 3, 15),
        "stale": date(2026, 5, 15),
    },
    "2026-06": {
        "fresh": date(2026, 6, 7),
        "mid": date(2026, 6, 18),
        "stale": date(2026, 8, 15),
    },
    "2026-07": {
        "fresh": date(2026, 6, 30),
        "mid": date(2026, 7, 20),
        "stale": date(2026, 9, 19),
    },
    "synthetic-2026-12": {
        "fresh": date(2026, 11, 30),
        "mid": date(2026, 12, 20),
        "stale": date(2027, 2, 20),
    },
}

# The best hint that could be written for the format, in the words a
# search_sources.extraction_hints row would carry.
HINT = (
    "This is a club calendar. A month name stands alone as a heading (for example 'Luglio'), "
    "and each entry under it starts with a weekday and a day of that month ('GIO 2' = Thursday "
    "the 2nd). When the day number drops back to 1, the next month has begun, even with no new "
    "heading. No year is printed: pick the year in which the printed weekdays are right. Dates "
    "here are never relative to today. If the heading's month is already over, every entry is "
    "past and must be skipped."
)

APPROACHES = ("llm", "llm_hint", "preparse_llm")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _blocks(text: str) -> list[str]:
    """Each entry's own lines, in page order — entry n of truth.csv is block n."""
    blocks: list[list[str]] = []
    for line in text.splitlines():
        if preparse.ENTRY.match(line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    return ["\n".join(block) for block in blocks]


def _match(
    name: str, when: str, blocks: list[str], truth: list[dict], taken: set[int]
) -> int | None:
    """The entry a draft is about: by its words, then by its date among equals.

    Several nights share a title ("Clamore" four times), so words alone would
    pin every one of them on the first.
    """
    wanted = [token for token in _norm(name).split() if len(token) >= 3]
    if not wanted:
        return None
    scored = []
    for index, block in enumerate(blocks):
        body = _norm(block)
        score = sum(token in body for token in wanted) / len(wanted)
        if score >= 0.6:
            scored.append((score, index))
    if not scored:
        return None
    best = max(score for score, _ in scored)
    equals = [index for score, index in scored if score == best]
    for index in equals:
        if truth[index]["date"] == when and index not in taken:
            return index
    free = [index for index in equals if index not in taken]
    return (free or equals)[0]


def _run(text: str, hint: str, today: date) -> list[dict]:
    class _Today(date):
        @classmethod
        def today(cls):
            return today

    # The prompt's "Today is ...", for the length of this one extraction.
    with patch.object(extraction, "date", _Today):
        # As the sweep would read it if Ink Club were vouched for: its entries
        # open with their date, raw ("GIO 2club") and resolved alike.
        drafts = extraction.extract_events_from_page(
            text, url=URL, city="Bergamo", hint=hint, vouched=True, date_first=True
        )
    return [
        {
            "name": draft.name or ", ".join(draft.artists),
            "start_at": draft.start_at or "",
        }
        for draft in drafts
    ]


def main() -> None:
    with (HERE / "truth.csv").open(encoding="utf-8-sig") as handle:
        truth_rows = list(csv.DictReader(handle, delimiter=";"))

    rows: list[dict] = []
    runs: list[dict] = []
    totals = {
        a: {"returned": 0, "good": 0, "harmful": 0, "false_future": 0, "harmless": 0}
        for a in APPROACHES
    }
    recall = {a: [0, 0] for a in APPROACHES}

    for page, days in SCENARIOS.items():
        text = (HERE / "pages" / f"{page}.txt").read_text(encoding="utf-8")
        truth = [row for row in truth_rows if row["page"] == page]
        blocks = _blocks(text)
        assert len(blocks) == len(truth), page

        for scenario, today in days.items():
            resolved, unresolved = preparse.resolve(text, today)
            inputs = {
                "llm": (text, ""),
                "llm_hint": (text, HINT),
                "preparse_llm": (resolved, ""),
            }
            found: dict[str, dict[int, str]] = {}
            strays: dict[str, list[dict]] = {}
            for approach in APPROACHES:
                drafts = _run(*inputs[approach], today)
                runs.append(
                    {
                        "page": page,
                        "scenario": scenario,
                        "today": today.isoformat(),
                        "approach": approach,
                        "drafts": drafts,
                    }
                )
                taken: set[int] = set()
                found[approach], strays[approach] = {}, []
                for draft in drafts:
                    when = draft["start_at"][:10]
                    index = _match(draft["name"], when, blocks, truth, taken)
                    if index is None or index in found[approach]:
                        strays[approach].append(draft)
                        continue
                    taken.add(index)
                    found[approach][index] = when
                print(
                    f"{page} {scenario:<5} {approach:<13} {len(drafts):>2} drafts",
                    flush=True,
                )

            for index, entry in enumerate(truth):
                upcoming = entry["date"] >= today.isoformat()
                row = {
                    "page": page,
                    "read_on": today.isoformat(),
                    "scenario": scenario,
                    "n": entry["n"],
                    "printed": f"{entry['weekday']} {entry['day']} {entry['tag']}".strip(),
                    "title": entry["title"],
                    "true_date": entry["date"],
                    "still_to_come": "yes" if upcoming else "no",
                    "music": entry["music"],
                }
                for approach in APPROACHES:
                    when = found[approach].get(index, "")
                    row[f"{approach}_date"] = when
                    if not when:
                        verdict = "not returned"
                    elif when == entry["date"]:
                        verdict = "right" if upcoming else "right (past, dropped later)"
                    elif when >= today.isoformat():
                        verdict = "WRONG, shown as upcoming"
                    else:
                        verdict = "wrong (past, dropped later)"
                    row[f"{approach}_result"] = verdict
                    totals[approach]["returned"] += bool(when)
                    totals[approach]["good"] += verdict == "right"
                    totals[approach]["harmful"] += verdict == "WRONG, shown as upcoming"
                    totals[approach]["false_future"] += (
                        verdict == "WRONG, shown as upcoming" and not upcoming
                    )
                    totals[approach]["harmless"] += verdict.endswith("dropped later)")
                    if upcoming and entry["music"] == "yes":
                        recall[approach][1] += 1
                        recall[approach][0] += verdict == "right"
                row["owner_verdict"] = ""
                row["owner_notes"] = ""
                rows.append(row)

            for approach in APPROACHES:
                for draft in strays[approach]:
                    when = draft["start_at"][:10]
                    shown = when >= today.isoformat()
                    rows.append(
                        {
                            "page": page,
                            "read_on": today.isoformat(),
                            "scenario": scenario,
                            "n": "",
                            "printed": "",
                            "title": f"[{approach}] {draft['name']}",
                            "true_date": "",
                            "still_to_come": "",
                            "music": "",
                            f"{approach}_date": when,
                            f"{approach}_result": "NO SUCH ENTRY, shown as upcoming"
                            if shown
                            else "no such entry (past, dropped later)",
                            "owner_verdict": "",
                            "owner_notes": "",
                        }
                    )
                    totals[approach]["returned"] += 1
                    totals[approach]["harmful"] += shown
                    totals[approach]["harmless"] += not shown

    fields = [
        "page",
        "read_on",
        "scenario",
        "n",
        "printed",
        "title",
        "true_date",
        "still_to_come",
        "music",
    ]
    for approach in APPROACHES:
        fields += [f"{approach}_date", f"{approach}_result"]
    fields += ["owner_verdict", "owner_notes"]
    # Semicolons and a BOM: it opens straight in an Italian or Spanish Excel.
    with (HERE / "results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", restval="")
        writer.writeheader()
        writer.writerows(rows)
    (HERE / "runs.json").write_text(
        json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    lines = [
        "| approach | drafts returned | right and still to come | WRONG and shown as upcoming | of those, past nights moved into the future | wrong or past, dropped by the sweep | music nights still to come that came back right |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for approach in APPROACHES:
        t, (hit, of) = totals[approach], recall[approach]
        lines.append(
            f"| {approach} | {t['returned']} | {t['good']} | {t['harmful']} | {t['false_future']} | "
            f"{t['harmless']} | {hit} of {of} |"
        )
    (HERE / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
