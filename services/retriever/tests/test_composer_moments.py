"""Composer moment handling — situation derivation + prompt/stream wiring.

The golden set here pins the *inputs* the composer receives per moment (the
situation label and ground truth), not the LLM's wording. Wording quality is
checked in the live smoke, not in unit tests.
"""

from unittest.mock import Mock

from laiive_shared import EventCard

from agent.classifier import Classification
from agent.composer import Composer, _situation

CARD = EventCard(
    uid="e1", name="Noche de Jazz", artists=["Marta Sánchez Trio"], source="seed"
)


def classification(query_type="event_search", moment="first_query", **kwargs):
    return Classification(query_type=query_type, moment=moment, **kwargs)


class TestSituationDerivation:
    def test_unsafe_wins_over_everything(self):
        assert _situation(classification(), [CARD], unsafe=True) == "unsafe"

    def test_smalltalk_and_out_of_scope_pass_through(self):
        assert (
            _situation(classification(query_type="smalltalk"), [], False) == "smalltalk"
        )
        assert (
            _situation(classification(query_type="out_of_scope"), [], False)
            == "out_of_scope"
        )

    def test_ambiguous_beats_empty(self):
        c = classification(moment="ambiguous", clarification="which city")
        assert _situation(c, [], False) == "ambiguous"

    def test_zero_results_is_empty(self):
        assert _situation(classification(), [], False) == "empty"

    def test_moments_pass_through_with_results(self):
        for moment in ("first_query", "refinement", "new_topic"):
            assert _situation(classification(moment=moment), [CARD], False) == moment


class FakeStream:
    """Mimics the OpenAI streaming iterator."""

    def __init__(self, tokens):
        self._tokens = tokens

    def __iter__(self):
        for token in self._tokens:
            chunk = Mock()
            chunk.choices = [Mock(delta=Mock(content=token))]
            yield chunk


class TestComposeStream:
    def _compose(self, tokens=("Three ", "jazz ", "nights."), **kwargs):
        client = Mock()
        client.chat.completions.create.return_value = FakeStream(list(tokens))
        composer = Composer(client=client)
        deltas = list(
            composer.compose_stream(
                kwargs.pop("user_message", "jazz in madrid?"),
                kwargs.pop("history", None),
                kwargs.pop("classification", classification()),
                kwargs.pop("cards", [CARD]),
                **kwargs,
            )
        )
        return deltas, client.chat.completions.create.call_args.kwargs

    def test_streams_deltas_in_order(self):
        deltas, call = self._compose()
        assert deltas == ["Three ", "jazz ", "nights."]
        assert call["stream"] is True

    def test_ground_truth_and_situation_reach_the_prompt(self):
        _, call = self._compose()
        context = call["messages"][-1]["content"]
        assert "Situation: first_query" in context
        assert "Noche de Jazz" in context

    def test_empty_results_change_the_situation(self):
        _, call = self._compose(cards=[])
        assert "Situation: empty" in call["messages"][-1]["content"]

    def test_clarification_forwarded_when_ambiguous(self):
        c = classification(moment="ambiguous", clarification="which city")
        _, call = self._compose(classification=c, cards=[])
        context = call["messages"][-1]["content"]
        assert "Situation: ambiguous" in context
        assert "which city" in context

    def test_reply_language_is_stated_last(self):
        # The Spanish event names in the ground truth are what used to decide
        # the reply language — the decided language has to come after them.
        _, call = self._compose(classification=classification(language="en"))
        context = call["messages"][-1]["content"]
        assert context.index("Noche de Jazz") < context.index("English (en)")

    def test_classifier_language_reaches_the_prompt(self):
        _, call = self._compose(classification=classification(language="ca"))
        assert "Catalan (ca)" in call["messages"][-1]["content"]

    def test_stream_failure_yields_graceful_text(self):
        client = Mock()
        client.chat.completions.create.side_effect = Exception("boom")
        composer = Composer(client=client)
        deltas = list(composer.compose_stream("hi", None, classification(), []))
        assert len(deltas) == 1  # one graceful fallback message, no raise
