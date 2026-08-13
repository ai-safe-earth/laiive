"""Convert voice, image, URL, and text inputs to structured event data."""

import base64
import json
import httpx
from openai import OpenAI
from loguru import logger
from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

EXTRACTION_PROMPT = """Extract event information from this text. Return a JSON object with ONLY the fields you can identify.

Possible fields: artist, date_time, venue, city, price, description, genre, ticket_url

Rules:
- artist: artist or band name (string)
- date_time: date and time in ISO format "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD HH:MM"
- venue: venue name (string)
- city: city name (string)
- price: numeric value only, no currency symbol (number or string like "25" or "free")
- description: short event description (string)
- genre: music genre slug (string, lowercase, e.g. "jazz", "electronic")
- ticket_url: URL string

Return ONLY a valid JSON object. No explanation, no markdown fences.

Text to extract from:
{text}"""


def audio_to_text(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using OpenAI Whisper."""
    response = _client.audio.transcriptions.create(
        model=settings.whisper_model,
        file=(filename, audio_bytes),
    )
    return response.text


def image_to_text(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Extract event information from an image using GPT-4o vision."""
    b64 = base64.b64encode(image_bytes).decode()
    response = _client.chat.completions.create(
        model=settings.conversation_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract all live music event information from this image. "
                            "Include: artist name, date and time, venue, city, price, "
                            "description, genre, and ticket URL if visible. "
                            "Return the information as plain text."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                ],
            }
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


def document_to_text(doc_bytes: bytes, filename: str) -> str:
    """Extract text from a PDF or document."""
    if filename.lower().endswith((".txt", ".csv", ".md")):
        return doc_bytes.decode("utf-8", errors="replace")
    return image_to_text(doc_bytes, mime_type="application/pdf")


def extract_fields_from_text(text: str) -> dict:
    """Use LLM to extract structured event fields from unstructured text."""
    response = _client.chat.completions.create(
        model=settings.conversation_model,
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.format(text=text)},
        ],
        temperature=0.0,
    )
    content = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        extracted = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse extraction response: {content[:200]}")
        return {}

    if not isinstance(extracted, dict):
        return {}

    return extracted


def extract_from_url(url: str, language: str = "en") -> dict:
    """Fetch a URL and extract event details from its content."""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as http:
            resp = http.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; laiive-bot/1.0)",
                },
            )
            resp.raise_for_status()
            page_text = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        raise ValueError(f"Could not fetch URL: {e}")

    # Truncate to avoid token limits
    max_chars = 8000
    if len(page_text) > max_chars:
        page_text = page_text[:max_chars]

    prompt = (
        f"Extract live music event information from this webpage content. "
        f"Language preference: {language}.\n\n"
        f"Webpage content:\n{page_text}"
    )

    return extract_fields_from_text(prompt)
