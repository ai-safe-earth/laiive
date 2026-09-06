"""Speech-to-text, shared by the retriever (public) and pusher (pro).

Both services turn a recording into plain text and then treat it exactly like
typed input, so the transcription call and — more importantly — the size policy
live here rather than being written twice with two different limits.

Like `neo4j_writer`, this module owns no API client: the caller passes its own,
which keeps each service's test patching in one place.
"""

from typing import Any

# Whisper's own hard limit is 25 MB. We stop well short of it: a minute of
# webm/opus from a browser is ~1 MB, and anonymous transcription is a metered
# cost the gateway quota alone does not bound (D7).
MAX_AUDIO_BYTES = 8 * 1024 * 1024

# Container formats the browser MediaRecorder and mobile clients actually send.
ALLOWED_AUDIO_SUFFIXES = (
    ".webm",
    ".ogg",
    ".oga",
    ".mp3",
    ".mp4",
    ".m4a",
    ".wav",
    ".mpga",
    ".mpeg",
    ".flac",
)


class AudioTooLarge(ValueError):
    """Recording exceeds MAX_AUDIO_BYTES."""


class UnsupportedAudioFormat(ValueError):
    """Filename does not carry a suffix Whisper accepts."""


def validate_audio(audio_bytes: bytes, filename: str) -> None:
    """Raise before spending an API call on something that cannot work."""
    if not audio_bytes:
        raise ValueError("Empty audio data")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise AudioTooLarge(
            f"Recording is {len(audio_bytes) // 1024} kB; the limit is "
            f"{MAX_AUDIO_BYTES // 1024} kB"
        )
    if not filename.lower().endswith(ALLOWED_AUDIO_SUFFIXES):
        raise UnsupportedAudioFormat(
            f"Unsupported audio format: {filename}. "
            f"Send one of {', '.join(ALLOWED_AUDIO_SUFFIXES)}"
        )


def transcribe(
    client: Any,
    audio_bytes: bytes,
    filename: str = "audio.webm",
    model: str = "whisper-1",
) -> str:
    """Validate, then transcribe. Returns the plain transcript."""
    validate_audio(audio_bytes, filename)
    response = client.audio.transcriptions.create(
        model=model,
        file=(filename, audio_bytes),
    )
    return response.text.strip()
