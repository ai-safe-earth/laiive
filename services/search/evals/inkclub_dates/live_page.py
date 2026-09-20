"""The test set that matches what the site shows: Ink Club's live calendar.

One page, 25 entries, the one a person can open and check line by line
(pages/2026-07.txt; truth in truth.csv, page "2026-07"). It is read on two
days:

- 30 June, as if the programme had just gone up. Every entry is still to
  come, so this checks the DATES, and which entries are let through as music.
- 19 September, the day it was fetched. The page was never updated, so every
  entry is over and the right answer is: nothing upcoming. This checks that
  nothing is invented or moved into the future.

Three ways of reading it, all with the production prompt - which since
search-v2 spells out what counts as live music (agent/extraction.py):

    llm        the page as fetched
    llm_hint   the page plus the best hint for its format
    preparse   the page with every date resolved in code (agent/preparse.py):
               what a sweep does with Ink Club

Run from services/search:
    PYTHONPATH=. uv run --no-sync python evals/inkclub_dates/live_page.py

About 20 small gpt-4o-mini calls. Writes live_page_results.csv (one row per
entry) and live_page_summary.md.
"""

import csv
import pathlib
import sys
from datetime import date

from agent import preparse

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from run_eval import HINT, _blocks, _match, _run  # noqa: E402 - beside this file

PAGE = "2026-07"
DAYS = {"30 Jun": date(2026, 6, 30), "19 Sep": date(2026, 9, 19)}

APPROACHES = ("llm", "llm_hint", "preparse")


def main() -> None:
    with (HERE / "truth.csv").open(encoding="utf-8-sig") as handle:
        truth = [
            row for row in csv.DictReader(handle, delimiter=";") if row["page"] == PAGE
        ]
    text = (HERE / "pages" / f"{PAGE}.txt").read_text(encoding="utf-8")
    blocks = _blocks(text)
    assert len(blocks) == len(truth) == 25

    # returned[approach][day] = {entry index: date given}, plus drafts that
    # match no entry on the page at all.
    returned: dict[str, dict[str, dict[int, str]]] = {a: {} for a in APPROACHES}
    strays: dict[str, dict[str, list[dict]]] = {a: {} for a in APPROACHES}
    for day, today in DAYS.items():
        resolved, unresolved = preparse.resolve(text, today)
        assert not unresolved, unresolved
        inputs = {
            "llm": (text, ""),
            "llm_hint": (text, HINT),
            "preparse": (resolved, ""),
        }
        for approach in APPROACHES:
            drafts = _run(*inputs[approach], today)
            found: dict[int, str] = {}
            lost: list[dict] = []
            taken: set[int] = set()
            for draft in drafts:
                when = draft["start_at"][:10]
                index = _match(draft["name"], when, blocks, truth, taken)
                if index is None or index in found:
                    lost.append(draft)
                    continue
                taken.add(index)
                found[index] = when
            returned[approach][day], strays[approach][day] = found, lost
            print(f"read {day}  {approach:<15} {len(drafts):>2} drafts", flush=True)

    rows = []
    for index, entry in enumerate(truth):
        row = {
            "n": entry["n"],
            "on the site": f"{entry['weekday']} {entry['day']} {entry['tag']}",
            "title": entry["title"],
            "true date": entry["date"],
            "music? (our label - yours to correct)": entry["music"],
        }
        for approach in APPROACHES:
            for day, today in DAYS.items():
                when = returned[approach][day].get(index, "")
                if when and when >= today.isoformat():
                    shown = "" if when == entry["date"] else "  WRONG"
                    cell = f"{when}{shown}"
                elif when:
                    cell = f"{when} (past, dropped)"
                else:
                    cell = "-"
                row[f"{approach} | read {day}"] = cell
        row["your verdict"] = ""
        rows.append(row)
    for approach in APPROACHES:
        for day, today in DAYS.items():
            for draft in strays[approach][day]:
                when = draft["start_at"][:10]
                rows.append(
                    {
                        "n": "",
                        "on the site": "NOT ON THE PAGE",
                        "title": draft["name"],
                        f"{approach} | read {day}": when
                        + (
                            "  SHOWN AS UPCOMING"
                            if when >= today.isoformat()
                            else " (past, dropped)"
                        ),
                        "your verdict": "",
                    }
                )

    fields = list(rows[0])
    with (HERE / "live_page_results.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", restval="")
        writer.writeheader()
        writer.writerows(rows)

    labels = [entry["music"] for entry in truth]
    music = {i for i, label in enumerate(labels) if label == "yes"}
    other = {i for i, label in enumerate(labels) if label == "no"}
    lines = [
        "Read on 30 June: all 25 entries still to come.",
        "",
        "| approach | right date | wrong date | not on the page | music nights kept (of "
        f"{len(music)}) | non-music let through (of {len(other)}) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for approach in APPROACHES:
        found = returned[approach]["30 Jun"]
        right = sum(when == truth[i]["date"] for i, when in found.items())
        lines.append(
            f"| {approach} | {right} | {len(found) - right} | {len(strays[approach]['30 Jun'])} | "
            f"{len(music & found.keys())} | {len(other & found.keys())} |"
        )
    lines += [
        "",
        "Read on 19 September: all 25 entries are over, so the right answer is nothing.",
        "",
        "| approach | shown as upcoming (should be 0) |",
        "| --- | --- |",
    ]
    cutoff = DAYS["19 Sep"].isoformat()
    for approach in APPROACHES:
        upcoming = sum(when >= cutoff for when in returned[approach]["19 Sep"].values())
        upcoming += sum(
            d["start_at"][:10] >= cutoff for d in strays[approach]["19 Sep"]
        )
        lines.append(f"| {approach} | {upcoming} |")
    (HERE / "live_page_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
