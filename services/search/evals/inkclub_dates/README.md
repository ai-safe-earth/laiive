# Can the sweep date Ink Club's calendar?

Ink Club (`inkclub.bergamo.it/calendario`) is the one Bergamo club page the
extractor could not be trusted with. The page reads fine; the dates do not. It
prints one month heading and then entries that open with a weekday and a day
("GIO 5#pub"), runs on into the next month with no new heading, and never
gives a year. Shown the live page on 2026-09-19 - still July's programme - the
model moved the nights to September and October, "2026-09-31" among them.

The question this folder answers: **does resolving those dates in code first,
and handing the model the dated text, do better than the model alone?** And a
second one, asked by the owner: most of the club's nights are not concerts -
**how are they kept out?**

## The test set: the page as the site shows it

`live_page.py` reads the one page a person can open and check line by line:
the live calendar, 25 entries, a "Luglio" heading that runs on into August
without saying so (`VEN 31` is 31 July; the `SAB 1` after it is 1 August, and
1 July was a Wednesday). It is read on two days - 30 June, when every night is
still to come, and 19 September, when the page was fetched and every night is
over, so the right answer is nothing. Results: `live_page_summary.md`, and
`live_page_results.csv` with one row per entry, in the site's order.

**Decided on 2026-09-19, from this set:** Ink Club is a vouched source, read
through `agent/preparse.py` (it moved there from this folder), and the
extraction prompt (search-v2) spells out what counts as live music. That list
was tried here first: the prompt used to say only "skip anything that is not
live music", and on this page that let all ten non-music nights through. With
the list, one or two get through, and 9 to 12 of the 12 music nights are kept,
varying from run to run - the ones dropped are nights whose title is not the
music ("LOCK IN: RESIDENZA ARTISTICA", then "a seguire ... OPEN JAM"). The
`preparse` approach below is now exactly what a sweep does.

What `music` means in `truth.csv` is two labellers' reading, not a decision:
three entries are `unsure`, and the owner's call overrules them.

Everything below this section - three more pages, three reading days - is the
wider regression set (`run_eval.py`). Two of those pages are older versions of
the calendar from the Wayback Machine and one is synthetic, so they are not what
the site shows today.

## The three approaches

| name | what the model is shown |
| --- | --- |
| `llm` | the page as fetched, no help. What production would do today. |
| `llm_hint` | the page as fetched, plus the best site hint that could be written (it is in `run_eval.py`). This is what a `search_sources.extraction_hints` row buys. |
| `preparse_llm` | the page with every entry line rewritten by `agent/preparse.py` as `2026-07-02 (giovedì 2 luglio 2026) club`. The model still decides what is live music, what it is called and who plays. |

All three use the production extractor, prompt and model
(`agent.extraction`, `gpt-4o-mini`), through the same code path a vouched page
takes in a sweep.

## The dataset

`pages/` holds the text exactly as Tavily's **advanced** extract returns it
(basic drops the day lines on two of the three, so advanced is needed whatever
else is decided):

| page | what it is | entries |
| --- | --- | --- |
| `2026-03.txt` | Wayback capture of 2026-03-06. March only. | 15 |
| `2026-06.txt` | Wayback capture of 2026-06-12. June only. | 15 |
| `2026-07.txt` | The live page on 2026-09-19. July running into August with no new heading, and one entry out of order at the end. | 25 |
| `synthetic-2026-12.txt` | **Synthetic.** March's real preamble and entries under a "Dicembre" heading, weekdays recomputed so every one is true, running into January 2027. No real page crosses a year, and that is the case most likely to break. | 15 |

Older Wayback captures (2023-2025) are of the club's previous site, which had
no calendar in its text; they are not usable.

`truth.csv` is the true date of every entry. For the three real pages it comes
from **two labellers working blind from each other**, each required to check
every weekday in Python; they agreed on all 55 dates. `music` is their shared
opinion of whether the entry is a music night (`unsure` where they differed or
could not tell) - it is only used for the last column of the summary, and it
is yours to overrule. The synthetic page's truth is known by construction.

Each page is read on three days, because the failure depends on the day:
`fresh` (the programme has just gone up), `mid` (half of it is over) and
`stale` (the club never took it down - how the live page was found).

## Reading the results

`summary.md` is the headline. `results.csv` is for you: one row per entry per
reading day, semicolon-separated with a BOM so it opens in Excel as it is.

- `true_date`, `still_to_come`, `music` - the truth, for that reading day.
- `<approach>_date` - the date that approach gave the entry, empty if it did
  not return it.
- `<approach>_result`:
  - `right` - right date, still to come. A good candidate.
  - `right (past, dropped later)` / `wrong (past, dropped later)` - the model
    returned a past night. The sweep's own past filter drops these, so they
    cost nothing but tokens.
  - **`WRONG, shown as upcoming`** - a wrong date that survives the past
    filter and would sit in a dry-run report as a new candidate. This is the
    one that matters.
  - `not returned` - fine for a past or non-music entry, a miss otherwise.
- Rows with no `n` and a title starting `[approach]` are drafts that match no
  entry on the page at all.
- `owner_verdict`, `owner_notes` - empty, for you.

`runs.json` keeps every draft of every call, so a row can be traced back.

## Re-running

```
cd services/search
PYTHONPATH=. uv run --no-sync python evals/inkclub_dates/run_eval.py
```

36 extractions (4 pages x 3 reading days x 3 approaches). Each page is read as
the sweep would read it if Ink Club were vouched for - in chunks of whole
entries, a few small calls each - so that is about a hundred `gpt-4o-mini`
calls: ten minutes and a few cents. No Tavily credits, nothing written outside
this folder. The model is not perfectly repeatable at temperature 0, so counts
can move by one or two between runs.

## What this folder also found

This evaluation was run three times, and the first two found faults in the
sweep's extractor rather than in anything about Ink Club.

1. The first run showed 8 wrong-and-upcoming rows for `preparse_llm`, all on
   the live page, and they were not the parser's dates. The extractor was then
   reading vouched pages in overlapping text windows; the dated text had grown
   past one window, and the second began just after an entry's date line. The
   model gave that title the NEXT entry's date and carried the slip on for four
   entries. The same fault was then measured on Eppen: 2 wrong dates of 48 at
   one cut, 9 of 41 at another.
2. The extractor was rebuilt to send the whole page every time and ask for its
   events twelve at a time. The second run showed what that does when a page
   runs out: asked for "the next twelve", the model did not answer "none". On
   the stale March page it re-listed March's nights with May dates, and on the
   stale live page it invented "HIP HOP NIGHT" and "REGGAE PARTY".
3. The extractor now cuts the text only where a line opens with a date, so
   every call sees whole entries and none is asked for "more"
   (`agent/extraction.py`). The results in this folder are from that.

So keep this folder as a regression check on the extractor, whatever is
decided about Ink Club: its stale pages are exactly the case - everything
past, nothing to return - that shows whether a change makes the model invent.
