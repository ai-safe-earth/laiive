"""The reply language is decided, not inferred — see laiive_shared.language."""

from unittest.mock import MagicMock

from laiive_shared.language import (
    DEFAULT_LANGUAGE,
    detect_language,
    normalize_language,
    reply_language_instruction,
)


def _client_returning(content):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    client.chat.completions.create.return_value = response
    return client


class TestNormalize:
    def test_plain_code(self):
        assert normalize_language("es") == "es"

    def test_case_and_region(self):
        assert normalize_language("EN-US") == "en"
        assert normalize_language("pt_BR") == "pt"

    def test_language_name(self):
        assert normalize_language("Spanish") == "es"

    def test_stray_punctuation(self):
        assert normalize_language(' "it". ') == "it"

    def test_garbage_falls_back(self):
        # The model ignoring the question must not poison the reply prompt.
        assert normalize_language('{"events": []}') == DEFAULT_LANGUAGE
        assert normalize_language("") == DEFAULT_LANGUAGE
        assert normalize_language(None) == DEFAULT_LANGUAGE


class TestInstruction:
    def test_names_the_language_and_overrides_content(self):
        text = reply_language_instruction("es")
        assert "Spanish (es)" in text
        assert "irrelevant" in text

    def test_unknown_code_still_usable(self):
        assert "(sv)" in reply_language_instruction("sv")


class TestDetect:
    def test_returns_the_detected_code(self):
        client = _client_returning("es")
        assert (
            detect_language(client, "gpt-4o-mini", "hola, tengo un concierto") == "es"
        )

    def test_proper_nouns_are_not_evidence(self):
        # The rule the prompt carries — pinned so a reword cannot drop it.
        client = _client_returning("en")
        detect_language(client, "gpt-4o-mini", "jazz in Madrid")
        prompt = client.chat.completions.create.call_args.kwargs["messages"][0][
            "content"
        ]
        assert "Proper nouns are NOT evidence" in prompt
        assert "jazz in Madrid" in prompt

    def test_empty_text_makes_no_call(self):
        client = _client_returning("es")
        assert detect_language(client, "gpt-4o-mini", "   ") == DEFAULT_LANGUAGE
        client.chat.completions.create.assert_not_called()

    def test_long_text_is_truncated(self):
        client = _client_returning("en")
        detect_language(client, "gpt-4o-mini", "x" * 5000)
        prompt = client.chat.completions.create.call_args.kwargs["messages"][0][
            "content"
        ]
        assert "x" * 600 in prompt
        assert "x" * 601 not in prompt

    def test_api_failure_answers_in_the_default(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("boom")
        assert detect_language(client, "gpt-4o-mini", "ciao") == DEFAULT_LANGUAGE
