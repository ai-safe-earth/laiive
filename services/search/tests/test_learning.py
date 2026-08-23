"""The source and query ranking: decay, promotion, and how it steers a sweep."""

import json

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
        assert discovery.plan_queries()[:4] == discovery.QUERY_TEMPLATES[:4]

    def test_one_slot_is_always_a_trial(self, mock_learning_http):
        planned = discovery.plan_queries()
        assert len(planned) == 5
        assert planned[-1] in discovery.TRIAL_TEMPLATES

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
        include, _ = learning.domain_filters()
        assert "drusobg.it" in include
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
        assert "drusobg.it" in narrowed[0]["include_domains"]

    def test_a_vouched_source_is_never_auto_blocked(self, mock_learning_http):
        """A quiet fortnight at Druso is an extraction problem to look at, not
        a verdict on the club."""
        store(
            mock_learning_http,
            sources=[{"domain": "drusobg.it", "status": "trusted", "pages": 20}],
        )
        learning.record_sources({"drusobg.it": {"pages": 20, "pages_with_events": 0}})
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
            call
            for call in mock_tavily.post.call_args_list
            if "extract" in call.args[0]
        ]
        assert len(extracts) == 1
        assert "https://drusobg.it/" in extracts[0].kwargs["json"]["urls"]
        # Basic, not advanced: half the price, and advanced failed outright on
        # drusobg.it/eventi/ where basic succeeded.
        assert extracts[0].kwargs["json"]["extract_depth"] == "basic"

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
        assert "drusobg.it" in read

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
                "failed_results": [{"url": "https://drusobg.it/", "error": "boom"}],
            }
        )
        assert tavily.extract(["https://drusobg.it/"]) == []
        assert tavily.extract_credits(0) == 0

    def test_extract_credit_arithmetic(self):
        from agent import tavily

        assert tavily.extract_credits(1) == 1
        assert tavily.extract_credits(5) == 1
        assert tavily.extract_credits(6) == 2
        assert tavily.extract_credits(6, "advanced") == 4
