"""The source and query ranking: decay, promotion, and how it steers a sweep."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import conftest
from agent import discovery, learning
from conftest import http_response


def store(mock_http, *, sources=None, queries=None):
    """Answer GETs by table, because one sweep reads both in an order the
    tests should not have to know."""

    def get(url, *args, **kwargs):
        if "search_sources" in url:
            return http_response(200, sources or [])
        if "search_queries" in url:
            return http_response(200, queries or [])
        return http_response(200, [])

    mock_http.get.side_effect = get


def posted(mock_http, table):
    """The rows upserted to one table across the whole call."""
    out = []
    for call in mock_http.post.call_args_list:
        if call.args and table in call.args[0]:
            out.extend(call.kwargs["json"])
    return out


class TestDecay:
    def test_a_burst_fades_instead_of_ranking_forever(self):
        """A three-week festival is real while it runs and misleading after.
        Straight accumulation would leave it top of the ranking in December."""
        row = {"pages": 100.0}
        for _ in range(14):
            row = learning._merged(row, {}, ("pages",))
        assert row["pages"] < 100 * 0.15

    def test_a_site_that_keeps_listing_holds_its_place(self):
        row = {"pages": 0.0}
        for _ in range(14):
            row = learning._merged(row, {"pages": 5}, ("pages",))
        # Converges to observed / (1 - DECAY) rather than growing without bound.
        assert 28 < row["pages"] < 34


class TestSourceStatus:
    def test_one_lucky_page_is_not_evidence(self):
        assert (
            learning._source_status({"pages": 1, "pages_with_events": 1}) == "candidate"
        )

    def test_a_site_that_keeps_yielding_is_trusted(self):
        assert (
            learning._source_status({"pages": 10, "pages_with_events": 6}) == "trusted"
        )

    def test_a_site_that_never_yields_is_blocked(self):
        assert (
            learning._source_status({"pages": 10, "pages_with_events": 0}) == "blocked"
        )

    def test_a_quiet_but_untested_site_is_left_alone(self):
        """Below the block threshold it stays a candidate: the sweep has not
        looked at it enough to say it is empty."""
        assert (
            learning._source_status({"pages": 3, "pages_with_events": 0}) == "candidate"
        )


class TestRecordSources:
    def test_an_owner_block_survives_a_good_week(self, mock_learning_http):
        """Blocked is the one verdict a human sets by hand, so yield must not
        quietly undo it."""
        store(
            mock_learning_http,
            sources=[{"domain": "junk.example", "status": "blocked", "pages": 0}],
        )
        learning.record_sources(
            {"junk.example": {"pages": 10, "pages_with_events": 9, "candidates_new": 9}}
        )
        (row,) = posted(mock_learning_http, "search_sources")
        assert row["status"] == "blocked"

    def test_hints_are_not_lost_by_the_upsert(self, mock_learning_http):
        """The write replaces the whole row, so anything the owner typed has to
        be carried through it."""
        store(
            mock_learning_http,
            sources=[
                {
                    "domain": "venue.example",
                    "status": "candidate",
                    "extraction_hints": "the agenda is the second table",
                }
            ],
        )
        learning.record_sources({"venue.example": {"pages": 1}})
        (row,) = posted(mock_learning_http, "search_sources")
        assert row["extraction_hints"] == "the agenda is the second table"

    def test_the_timestamps_are_timestamps(self, mock_learning_http):
        """Both tables shipped `"now()"` as a literal string. PostgREST sends
        the value as JSON, so Postgres received the six characters and refused
        to cast them — and _upsert raises, which the sweep catches and logs as
        a warning, so the whole learning loop was dead behind one line."""
        store(mock_learning_http)
        learning.record_sources({"venue.example": {"pages": 1}})
        learning.record_queries({"conciertos madrid": {"candidates_new": 1}})
        (source,) = posted(mock_learning_http, "search_sources")
        (query,) = posted(mock_learning_http, "search_queries")
        for value in (source["last_seen_at"], query["last_used_at"]):
            datetime.fromisoformat(value)


class TestQueryPromotion:
    def test_a_trial_that_beats_the_standing_median_is_promoted(
        self, mock_learning_http
    ):
        store(
            mock_learning_http,
            queries=[
                {
                    "template": "a",
                    "status": "standing",
                    "runs": 5,
                    "candidates_new": 10,
                },
                {"template": "b", "status": "trial", "runs": 5, "candidates_new": 20},
            ],
        )
        learning.promote_queries()
        changed = {
            r["template"]: r["status"]
            for r in posted(mock_learning_http, "search_queries")
        }
        assert changed == {"b": "standing"}

    def test_a_phrasing_is_not_judged_before_it_has_run(self, mock_learning_http):
        """One quiet week in one town must not retire a good phrasing."""
        store(
            mock_learning_http,
            queries=[
                {
                    "template": "a",
                    "status": "standing",
                    "runs": 9,
                    "candidates_new": 90,
                },
                {"template": "b", "status": "trial", "runs": 1, "candidates_new": 0},
            ],
        )
        learning.promote_queries()
        assert posted(mock_learning_http, "search_queries") == []

    def test_a_standing_phrasing_that_stops_earning_retires(self, mock_learning_http):
        store(
            mock_learning_http,
            queries=[
                {
                    "template": "a",
                    "status": "standing",
                    "runs": 5,
                    "candidates_new": 50,
                },
                {"template": "b", "status": "standing", "runs": 5, "candidates_new": 0},
            ],
        )
        learning.promote_queries()
        changed = {
            r["template"]: r["status"]
            for r in posted(mock_learning_http, "search_queries")
        }
        assert changed["b"] == "retired"


class TestTrialSelection:
    def test_the_least_tested_phrasing_gets_the_slot(self, mock_learning_http):
        store(
            mock_learning_http,
            queries=[
                {"template": "a", "status": "trial", "runs": 4},
                {"template": "b", "status": "trial", "runs": 1},
            ],
        )
        assert learning.select_trial(["a", "b", "c"]) == "c"  # c has never run

    def test_a_retired_phrasing_never_comes_back(self, mock_learning_http):
        store(
            mock_learning_http,
            queries=[{"template": "a", "status": "retired", "runs": 0}],
        )
        assert learning.select_trial(["a"]) is None


class TestSteeringTheSweep:
    def test_a_fresh_database_sweeps_exactly_as_before(self, mock_learning_http):
        """Nothing learned yet is the normal first-run state, and it must not
        change what the sweep does."""
        templates, trial = discovery.plan_queries()
        assert templates[:4] == discovery.QUERY_TEMPLATES[:4]
        # The fifth file template now arrives through the trial slot, so a
        # fresh store still runs all five phrasings the file promises.
        assert trial == discovery.QUERY_TEMPLATES[4]

    def test_one_slot_is_always_a_trial(self, mock_learning_http):
        planned, trial = discovery.plan_queries()
        assert len(planned) == 5
        assert planned[-1] == trial
        assert trial in discovery.TRIAL_TEMPLATES

    def test_known_empty_domains_are_excluded_from_every_query(
        self, mock_learning_http, mock_tavily
    ):
        store(
            mock_learning_http,
            sources=[{"domain": "junk.example", "status": "blocked"}],
        )
        discovery.sweep_city("Torino")
        for call in mock_tavily.post.call_args_list:
            assert call.kwargs["json"]["exclude_domains"] == ["junk.example"]

    def test_trusted_domains_narrow_one_slot_and_only_one(
        self, mock_learning_http, mock_tavily
    ):
        """A search restricted to the sites it already knows can only confirm
        them, so the other slots stay open or the list closes on itself."""
        store(
            mock_learning_http,
            sources=[
                {"domain": f"good{i}.example", "status": "trusted"} for i in range(3)
            ],
        )
        discovery.sweep_city("Torino")
        narrowed = [
            call
            for call in mock_tavily.post.call_args_list
            if "include_domains" in call.kwargs["json"]
        ]
        assert len(narrowed) == 1

    def test_thin_evidence_does_not_narrow_anything(
        self, mock_learning_http, mock_tavily, monkeypatch
    ):
        """The focused slot needs three trusted domains. The vouched seeds meet
        that on their own, so this checks the guard itself with none of them --
        one lucky domain must not be allowed to become the whole search."""
        monkeypatch.setattr(learning, "SEED_SOURCES", {})
        store(
            mock_learning_http,
            sources=[{"domain": "good.example", "status": "trusted"}],
        )
        discovery.sweep_city("Torino")
        assert not any(
            "include_domains" in call.kwargs["json"]
            for call in mock_tavily.post.call_args_list
        )

    def test_a_store_outage_does_not_lose_the_sweep(
        self, mock_learning_http, mock_tavily
    ):
        """The ranking is an optimisation for next time, never a dependency."""
        mock_learning_http.get.side_effect = RuntimeError("supabase down")
        mock_learning_http.post.side_effect = RuntimeError("supabase down")
        result = discovery.sweep_city("Torino")
        assert result.candidates


class TestExtractionHints:
    def test_a_sites_note_reaches_the_prompt(self, mock_learning_http, mock_openai):
        store(
            mock_learning_http,
            sources=[
                {
                    "domain": "example.com",
                    "status": "candidate",
                    "extraction_hints": "the agenda is the second table",
                }
            ],
        )
        discovery.sweep_city("Torino")
        prompts = "".join(
            call.kwargs["messages"][0]["content"]
            for call in mock_openai.chat.completions.create.call_args_list
        )
        assert "the agenda is the second table" in prompts

    def test_no_note_leaves_no_empty_heading(self, mock_learning_http, mock_openai):
        """An empty "Notes on this site:" reads as an instruction to find
        something that is not there."""
        discovery.sweep_city("Torino")
        prompts = "".join(
            call.kwargs["messages"][0]["content"]
            for call in mock_openai.chat.completions.create.call_args_list
        )
        assert "Notes on this site" not in prompts
        assert json.loads  # keeps the import honest


class TestWriteBack:
    def test_an_approved_event_counts_for_its_source(self, mock_learning_http):
        store(
            mock_learning_http,
            sources=[
                {"domain": "venue.example", "status": "candidate", "events_written": 2}
            ],
        )
        learning.record_writes(["venue.example", "venue.example"])
        (row,) = posted(mock_learning_http, "search_sources")
        assert row["events_written"] == 4

    def test_a_domain_the_sweep_never_saw_is_not_invented(self, mock_learning_http):
        """A row with a write and no pages behind it would rank on nothing."""
        learning.record_writes(["stranger.example"])
        assert posted(mock_learning_http, "search_sources") == []

    def test_a_store_outage_does_not_fail_the_approve(self, mock_learning_http):
        mock_learning_http.get.side_effect = RuntimeError("supabase down")
        learning.record_writes(["venue.example"])  # must not raise


class TestSeedSources:
    def test_a_vouched_source_is_included_before_anything_is_learned(
        self, mock_learning_http
    ):
        """The point of vouching: the ranking otherwise has to find a good site
        by accident before it can prefer it."""
        include, _ = learning.domain_filters("Bergamo")
        assert "drusobg.com" in include
        assert "dastebergamo.com" in include
        assert "ecodibergamo.it" in include

    def test_they_are_enough_to_open_the_focused_slot(
        self, mock_learning_http, mock_tavily
    ):
        """Three trusted domains is the threshold, and the seeds meet it on the
        first sweep of a fresh database."""
        discovery.sweep_city("Bergamo")
        narrowed = [
            call.kwargs["json"]
            for call in mock_tavily.post.call_args_list
            if "include_domains" in call.kwargs["json"]
        ]
        assert len(narrowed) == 1
        assert "drusobg.com" in narrowed[0]["include_domains"]

    def test_a_vouched_source_is_never_auto_blocked(self, mock_learning_http):
        """A quiet fortnight at Druso is an extraction problem to look at, not
        a verdict on the club."""
        store(
            mock_learning_http,
            sources=[{"domain": "drusobg.com", "status": "trusted", "pages": 20}],
        )
        learning.record_sources({"drusobg.com": {"pages": 20, "pages_with_events": 0}})
        (row,) = posted(mock_learning_http, "search_sources")
        assert row["status"] == "trusted"

    def test_the_arithmetic_still_blocks_everyone_else(self, mock_learning_http):
        learning.record_sources({"junk.example": {"pages": 20, "pages_with_events": 0}})
        (row,) = posted(mock_learning_http, "search_sources")
        assert row["status"] == "blocked"

    def test_a_subdomain_of_a_vouched_source_counts_too(self):
        assert learning._seeded("eventi.ecodibergamo.it")
        assert not learning._seeded("notecodibergamo.it")


class TestVouchedAgendas:
    def test_a_vouched_agenda_is_fetched_not_searched_for(
        self, mock_learning_http, mock_tavily
    ):
        """Search cannot read these pages -- restricted to the three domains it
        answered with 106-156 characters each. Extract returns the agenda."""
        discovery.sweep_city("Bergamo")
        extracts = [
            call.kwargs["json"]
            for call in mock_tavily.post.call_args_list
            if "extract" in call.args[0]
        ]
        # One call per depth in use, never one per page.
        assert len(extracts) == 2
        druso = next(
            e for e in extracts if "https://www.drusobg.com/event-list" in e["urls"]
        )
        # Basic, not advanced: half the price, and advanced failed outright on
        # drusobg.it/eventi/ where basic succeeded.
        assert druso["extract_depth"] == "basic"

    def test_a_city_with_no_vouched_source_does_not_extract(
        self, mock_learning_http, mock_tavily
    ):
        """Torino has no seeds, and the credit must not be spent on nothing."""
        discovery.sweep_city("Torino")
        assert not any(
            "extract" in call.args[0] for call in mock_tavily.post.call_args_list
        )

    def test_the_agenda_survives_the_page_budget(self, mock_learning_http, mock_openai):
        """max_pages truncates, and a page someone vouched for is the last one
        that should fall off the end."""
        discovery.sweep_city("Bergamo", max_pages=1)
        read = "".join(
            call.kwargs["messages"][0]["content"]
            for call in mock_openai.chat.completions.create.call_args_list
        )
        assert "drusobg.com" in read

    def test_the_extract_is_billed_in_the_report(self, mock_learning_http):
        """One credit per five successful extractions, on top of the five
        search slots -- and only for the cities that have a vouched agenda."""
        bergamo = discovery.sweep_city("Bergamo")
        torino = discovery.sweep_city("Torino")
        assert bergamo.stats["tavily_credits"] == 6
        assert torino.stats["tavily_credits"] == 5

    def test_a_page_that_cannot_be_fetched_is_not_billed(self, mock_tavily):
        """Tavily bills successful extractions only."""
        from agent import tavily

        mock_tavily.post.side_effect = None
        mock_tavily.post.return_value = http_response(
            payload={
                "results": [],
                "failed_results": [
                    {"url": "https://www.drusobg.com/event-list", "error": "boom"}
                ],
            }
        )
        assert tavily.extract(["https://www.drusobg.com/event-list"]) == []
        assert tavily.extract_credits(0) == 0

    def test_extract_credit_arithmetic(self):
        from agent import tavily

        assert tavily.extract_credits(1) == 1
        assert tavily.extract_credits(5) == 1
        assert tavily.extract_credits(6) == 2
        assert tavily.extract_credits(6, "advanced") == 4


def _prompts(mock_openai) -> list[str]:
    return [
        call.kwargs["messages"][0]["content"]
        for call in mock_openai.chat.completions.create.call_args_list
    ]


def _reply(*events: dict) -> MagicMock:
    """One extraction call's answer."""
    reply = MagicMock()
    reply.choices = [MagicMock()]
    reply.choices[0].message.content = json.dumps({"events": list(events)})
    return reply


def _night(name: str, **fields) -> dict:
    return {
        "name": name,
        "venue": "Daste",
        "city": "Bergamo",
        "start_at": "2027-04-01T21:00:00",
        **fields,
    }


class TestVouchedPagesAreReadInWholeEntries:
    """The model skims a long list, so a long listing is shown a little at a
    time — and everything turns on where the text is cut. Overlapping character
    windows mis-dated the entries at their edges, and asking for a page's events
    a batch at a time made the model invent nights once the page ran out. So
    the text is cut only where a line opens with a date."""

    # Eppen's shape: a preamble, then entries that each open with their date.
    LISTING = "Menu / Cerca eventi\n" + "".join(
        f"{day} Sab Settembre h.21:00 / 23:00\nSala {day} Bergamo\n\nSerata numero {day}\n"
        + "Una serata di musica dal vivo. " * 12
        + "\nMusica\n"
        for day in range(1, 13)
    )
    # Daste's shape: a dated archive first, well past any cap, and the one
    # thing worth reading at the very end.
    ARCHIVE = (
        "Il 16 novembre A SHOT IN THE DARK "
        + "archivio 12.03.2021 " * 2000
        + "IN-PROGRAMMA 19.09 | The Jazz Room"
    )
    DASTE = {"url": "https://www.dastebergamo.com/eventi/", "raw_content": ARCHIVE}

    def test_the_text_is_cut_only_where_a_line_opens_with_a_date(self):
        from agent import extraction

        chunks = extraction._entry_chunks(self.LISTING)
        assert len(chunks) > 2
        # Nothing lost, nothing repeated: no overlap, so no entry is seen twice.
        assert "".join(chunks) == self.LISTING
        for chunk in chunks[1:]:
            assert chunk.split(" ")[1] == "Sab", chunk[:40]
        # Every entry is whole in its chunk: its date line and its title together.
        for day in range(1, 13):
            home = [c for c in chunks if f"Serata numero {day}\n" in c]
            assert len(home) == 1
            assert f"{day} Sab Settembre" in home[0]

    def test_a_date_first_page_is_read_a_chunk_at_a_time(self, mock_openai):
        from agent import extraction

        chunks = extraction._entry_chunks(self.LISTING)
        mock_openai.chat.completions.create.side_effect = [
            _reply(_night(f"Night {i}")) for i in range(len(chunks))
        ]
        drafts = extraction.extract_events_from_page(
            self.LISTING,
            url="https://x.com",
            city="Bergamo",
            vouched=True,
            date_first=True,
        )
        # Every chunk's nights add up, and each call saw its own chunk only.
        assert [draft.name for draft in drafts] == [
            f"Night {i}" for i in range(len(chunks))
        ]
        prompts = _prompts(mock_openai)
        assert len(prompts) == len(chunks)
        assert (
            "Serata numero 1\n" in prompts[0] and "Serata numero 12\n" not in prompts[0]
        )
        assert "Serata numero 12\n" in prompts[-1]

    def test_a_page_that_does_not_say_date_first_is_one_call(self, mock_openai):
        """It is the source's to say, never guessed: on a page that puts the
        title first, a cut at a date line parts every title from its date."""
        from agent import extraction
        from config import settings

        text = self.LISTING * 4
        assert len(text) > settings.page_max_chars
        extraction.extract_events_from_page(
            text, url="https://x.com", city="Bergamo", vouched=True
        )
        prompts = _prompts(mock_openai)
        assert len(prompts) == 1
        assert len(prompts[0]) < settings.page_max_chars + 4000

    def test_a_page_costs_a_bounded_number_of_calls(self, mock_openai):
        from agent import extraction

        extraction.extract_events_from_page(
            self.LISTING * 40,
            url="https://x.com",
            city="Bergamo",
            vouched=True,
            date_first=True,
        )
        assert (
            mock_openai.chat.completions.create.call_count
            == extraction.AGENDA_MAX_CHUNKS
        )

    def test_a_page_with_its_programme_at_the_end_is_read_from_the_end(
        self, mock_learning_http, mock_tavily, mock_openai, monkeypatch
    ):
        """Not the head, which found nothing every sweep — and not the whole
        page either: the 2021 entries give a day and no year, and the model
        dated "Il 16 novembre" as next November's gig."""
        monkeypatch.setitem(conftest.TAVILY_EXTRACT_PAYLOAD, "results", [self.DASTE])
        mock_tavily.post.return_value = http_response(payload={"results": []})

        discovery.sweep_city("Bergamo")
        daste = [p for p in _prompts(mock_openai) if "dastebergamo.com" in p]
        assert len(daste) == 1
        assert "IN-PROGRAMMA 19.09 | The Jazz Room" in daste[0]
        assert "A SHOT IN THE DARK" not in daste[0]

    def test_a_source_that_does_not_say_so_is_read_from_its_start(self):
        text = "x" * 50000
        assert learning.programme_of("livemusicdieci10.it", text) == text
        assert learning.programme_of("example.com", text) == text
        assert len(learning.programme_of("dastebergamo.com", text)) == 4000

    def test_a_vouched_page_that_lost_its_dates_is_not_read(self, mock_openai):
        """Tavily's advanced extract sometimes answers with its basic text, and
        Eppen's then has titles and blurbs and no dates. Read anyway, the model
        dated the titles Oct 1, Oct 2, Oct 3 down the list."""
        from agent import extraction

        text = "Papa Roach – Rise Of The Roach / Fiorella Mannoia in concerto / " * 120
        drafts = extraction.extract_events_from_page(
            text, url="https://x.com", city="Bergamo", vouched=True, date_first=True
        )
        assert drafts == []
        assert mock_openai.chat.completions.create.call_count == 0

    def test_what_counts_as_a_date(self):
        from agent import extraction

        for dated in (
            "GIO 2club",  # Ink Club: the tag is glued to the day
            "19 Sab Settembre h.11:00",  # Eppen
            "sab 19 set",  # Druso
            "18.09.26 ROCK NIGHT",  # Dieci10
            "Venerdì 18.09.2026 | h 21.30",  # Daste
            "2026-07-02 (giovedì 2 luglio 2026) club",  # the pre-parsed calendar
            "Sept 19 at the arena",
        ):
            assert extraction._dated(dated), dated
        # An hour is not a date, and nor is a year on its own.
        for undated in (
            "dalle 21.30",
            "h 22:00",
            "Sonus Loci 2026",
            "ingresso 10 euro",
        ):
            assert not extraction._dated(undated), undated

    def test_a_searched_page_is_still_one_call_cut_at_the_cap(
        self, mock_learning_http, mock_tavily, mock_openai
    ):
        """Nobody vouched for it, and it is one of twenty-five."""
        mock_tavily.post.return_value = http_response(
            payload={
                "results": [
                    {
                        "url": "https://example.com/agenda",
                        "content": "snippet",
                        "raw_content": self.ARCHIVE,
                        "score": 0.9,
                    }
                ]
            }
        )
        discovery.sweep_city("Torino")
        prompts = _prompts(mock_openai)
        assert len(prompts) == 1
        assert "IN-PROGRAMMA" not in prompts[0]

    def test_a_search_hit_does_not_displace_the_vouched_copy(
        self, mock_learning_http, mock_tavily, mock_openai
    ):
        """Search surfaces these sites and cannot read them. When it returned a
        vouched URL first, its snippet was kept and the fetched page dropped as
        already seen."""
        mock_tavily.post.return_value = http_response(
            payload={
                "results": [
                    {
                        "url": "https://www.drusobg.com/event-list",
                        "content": "snippet",
                        "raw_content": "SEARCH-SNIPPET",
                        "score": 0.9,
                    }
                ]
            }
        )
        discovery.sweep_city("Bergamo")
        druso = [p for p in _prompts(mock_openai) if "drusobg.com" in p]
        assert len(druso) == 1
        # What the /extract fake answers with for this URL, and only that.
        assert "DRUSO agenda" in druso[0]
        assert "SEARCH-SNIPPET" not in druso[0]

    def test_each_source_is_fetched_at_its_own_depth(
        self, mock_learning_http, mock_tavily
    ):
        """Basic strips Eppen's listing to titles — no date, hour, venue or
        town — and the model then dated every event "tomorrow". Advanced keeps
        them, at twice the price, so it is per source and not for everyone:
        it failed outright on Druso's old site, where basic worked."""
        discovery.sweep_city("Bergamo")
        asked = {
            call.kwargs["json"]["extract_depth"]: call.kwargs["json"]["urls"]
            for call in mock_tavily.post.call_args_list
            if "extract" in call.args[0]
        }
        assert any("category=musica" in url for url in asked["advanced"])
        # Basic dropped Ink Club's day lines on both archived versions.
        assert "https://www.inkclub.bergamo.it/calendario" in asked["advanced"]
        assert not any("ecodibergamo.it" in url for url in asked["basic"])
        assert not any("inkclub" in url for url in asked["basic"])
        assert "https://livemusicdieci10.it/" in asked["basic"]

    def test_a_weekday_calendar_reaches_the_model_already_dated(
        self, mock_learning_http, mock_tavily, mock_openai, monkeypatch
    ):
        """Shown "GIO 2" under "Luglio" as printed, the model moved July's
        nights to September. The source says so, and the dates are resolved
        before the page is read."""
        page = "Luglio\nGIO 2club\ndalle 22:00\nPUNK ROCK RADUNO\n#liveband\n"
        monkeypatch.setitem(
            conftest.TAVILY_EXTRACT_PAYLOAD,
            "results",
            [{"url": "https://www.inkclub.bergamo.it/calendario", "raw_content": page}],
        )
        mock_tavily.post.return_value = http_response(payload={"results": []})
        discovery.sweep_city("Bergamo")
        ink = [p for p in _prompts(mock_openai) if "inkclub.bergamo.it" in p]
        assert len(ink) == 1
        assert "(giovedì 2 luglio" in ink[0]
        assert "\nGIO 2club" not in ink[0]

    def test_only_the_sources_that_say_so_are_read_in_chunks(self):
        assert learning.date_first("ecodibergamo.it")
        # Druso puts the title first ("NAME / sab 19 set / Druso").
        assert not learning.date_first("drusobg.com")
        assert not learning.date_first("example.com")

    def test_advanced_pages_are_billed_at_the_advanced_rate(
        self, mock_learning_http, monkeypatch
    ):
        monkeypatch.setitem(
            conftest.TAVILY_EXTRACT_PAYLOAD,
            "results",
            [
                {"url": url, "raw_content": "x"}
                for url in learning.agenda_urls("Bergamo", "advanced")
            ],
        )
        # Five search slots, plus two credits for up to five advanced pages.
        assert discovery.sweep_city("Bergamo").stats["tavily_credits"] == 7


class TestTrialSlotIntegrity:
    def test_a_promoted_phrasing_leaves_the_trial_pool(self, mock_learning_http):
        """Standing already earns a slot; keeping it trial-eligible ran the
        identical query twice in one sweep and double-counted its runs."""
        store(
            mock_learning_http,
            queries=[
                {"template": "a", "status": "standing", "runs": 1},
                {"template": "b", "status": "candidate", "runs": 5},
            ],
        )
        assert learning.select_trial(["a", "b"]) == "b"

    def test_all_promoted_or_retired_means_no_trial(self, mock_learning_http):
        store(
            mock_learning_http,
            queries=[
                {"template": "a", "status": "standing", "runs": 1},
                {"template": "b", "status": "retired", "runs": 9},
            ],
        )
        assert learning.select_trial(["a", "b"]) is None


class TestSeedsAreLocal:
    def test_another_citys_seeds_do_not_narrow_this_sweep(self, mock_learning_http):
        """All three seeds are Bergamo's. Prepending them for every city made
        the first-slot focus fire everywhere, so Torino's best query ran
        restricted to Bergamo-only sites — a guaranteed zero that then counted
        against the phrasing's yield."""
        include, _ = learning.domain_filters("Torino")
        assert include == []

    def test_a_citys_own_seeds_still_hold_from_the_first_sweep(
        self, mock_learning_http
    ):
        include, _ = learning.domain_filters("Bergamo")
        assert include[:3] == ["drusobg.com", "dastebergamo.com", "ecodibergamo.it"]
