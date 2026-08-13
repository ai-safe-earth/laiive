"""Speech-to-text policy: the size cap and format guard both services rely on.

Voice is public (D7), so these limits are the only thing between an anonymous
caller and a metered Whisper bill — they are checked before the API call, not
after it.
"""

from unittest.mock import MagicMock

import pytest
from laiive_shared.speech import (
    MAX_AUDIO_BYTES,
    AudioTooLarge,
    UnsupportedAudioFormat,
    transcribe,
    validate_audio,
)


def fake_client(text: str = "  jazz in madrid  ") -> MagicMock:
    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(text=text)
    return client


class TestValidation:
    def test_accepts_a_normal_recording(self):
        validate_audio(b"x" * 1024, "audio.webm")

    def test_rejects_empty_audio(self):
        with pytest.raises(ValueError):
            validate_audio(b"", "audio.webm")

    def test_rejects_oversized_audio(self):
        with pytest.raises(AudioTooLarge):
            validate_audio(b"x" * (MAX_AUDIO_BYTES + 1), "audio.webm")

    def test_rejects_unknown_container(self):
        with pytest.raises(UnsupportedAudioFormat):
            validate_audio(b"x" * 10, "recording.aiff")

    @pytest.mark.parametrize("name", ["a.webm", "a.MP3", "a.m4a", "a.wav", "a.ogg"])
    def test_accepts_browser_and_mobile_containers(self, name):
        validate_audio(b"x" * 10, name)


class TestTranscribe:
    def test_returns_stripped_text(self):
        client = fake_client()
        assert transcribe(client, b"audio-bytes", "audio.webm") == "jazz in madrid"

    def test_passes_model_and_filename_through(self):
        client = fake_client()
        transcribe(client, b"audio-bytes", "note.m4a", "whisper-1")
        kwargs = client.audio.transcriptions.create.call_args.kwargs
        assert kwargs["model"] == "whisper-1"
        assert kwargs["file"] == ("note.m4a", b"audio-bytes")

    def test_does_not_call_the_api_when_validation_fails(self):
        client = fake_client()
        with pytest.raises(AudioTooLarge):
            transcribe(client, b"x" * (MAX_AUDIO_BYTES + 1), "audio.webm")
        client.audio.transcriptions.create.assert_not_called()
