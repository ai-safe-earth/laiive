"""Extraction entry → EventDraft, where a missing price used to mean free.

The coercion is deliberately tolerant of what an LLM returns, and that
tolerance had a hole: an empty string went to 0.0, which the card renders as
"free". 48 of 57 discovered events said free, among them stadium shows with a
ticket link.
"""

from laiive_shared.drafts import entry_to_draft

BASE = {
    "name": "A show",
    "start_at": "2026-08-29T20:00:00",
    "venue": "Berghain",
    "city": "Berlin",
}


class TestPriceIsNotAssumed:
    def test_an_empty_price_is_not_stated(self):
        draft = entry_to_draft({**BASE, "price_min": ""})
        assert draft.price_min is None

    def test_a_price_the_page_never_mentioned_is_not_stated(self):
        assert entry_to_draft(BASE).price_min is None

    def test_a_page_that_says_free_still_means_free(self):
        for word in ("free", "Gratis", " ENTRADA LIBRE ", "0"):
            assert entry_to_draft({**BASE, "price_min": word}).price_min == 0.0

    def test_a_real_price_survives_its_formatting(self):
        assert entry_to_draft({**BASE, "price_min": "22,50"}).price_min == 22.5
        assert entry_to_draft({**BASE, "price_min": 15}).price_min == 15

    def test_an_unparseable_price_is_dropped_not_zeroed(self):
        assert (
            entry_to_draft({**BASE, "price_min": "from about twenty"}).price_min is None
        )
