"""Classifier unit tests — the LLM call is mocked; what is pinned is the
resolution of "today", which is not the model's job and must not drift."""

from datetime import datetime, timedelta, timezone as utc_timezone
from unittest.mock import Mock

from agent.classifier import Classifier, now_in


class TestNowIn:
    def test_reads_the_clock_in_the_given_zone(self):
        madrid = now_in("Europe/Madrid")
        assert madrid.tzinfo is not None
        assert madrid.utcoffset() in (timedelta(hours=1), timedelta(hours=2))

    def test_two_zones_can_disagree_about_the_date(self):
        """The whole point: at some instant every day, "today" differs by zone.
        Auckland is 11-13h ahead of Los Angeles, so their civil dates differ
        for roughly half of each day."""
        ahead = now_in("Pacific/Auckland")
        behind = now_in("America/Los_Angeles")
        assert (ahead - behind).total_seconds() < 1  # same instant
        assert ahead.utcoffset() != behind.utcoffset()  # different clocks

    def test_no_zone_falls_back_to_utc(self):
        assert now_in(None).utcoffset() == timedelta(0)

    def test_junk_from_a_client_does_not_fail_the_turn(self):
        """A client is free to send nonsense; the turn still has to answer."""
        for junk in ("Mars/Olympus", "", "not a zone", "UTC+2"):
            assert now_in(junk or None).utcoffset() is not None


class TestTodayInjection:
    def _classify_with(self, timezone):
        """Run one classification and return the system prompt it built."""
        client = Mock()
        client.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"query_type": "smalltalk", "moment": "first_query",'
                        ' "language": "en", "sub_queries": []}'
                    )
                )
            ]
        )
        Classifier(client).classify("hola", timezone=timezone)
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        return messages[0]["content"]

    def test_the_prompt_carries_the_askers_date_not_the_servers(self):
        prompt = self._classify_with("Pacific/Auckland")
        expected = now_in("Pacific/Auckland").date().isoformat()
        assert f"Today is {expected}" in prompt

    def test_the_weekday_matches_that_same_date(self):
        """A date and a weekday that disagree is worse than either alone —
        the model resolves "this weekend" off the weekday."""
        prompt = self._classify_with("Pacific/Auckland")
        now = now_in("Pacific/Auckland")
        assert f"Today is {now.date().isoformat()} ({now.strftime('%A')})" in prompt

    def test_no_timezone_uses_utc(self):
        prompt = self._classify_with(None)
        assert f"Today is {datetime.now(utc_timezone.utc).date().isoformat()}" in prompt
