"""Convert voice, image, URL, and text inputs into an EventDraft.

The one extraction prompt for every modality (04-plan: the duplicated
prompts/functions merged here). Everything funnels into `EventDraft`.
"""

import base64
import json
from datetime import date

import httpx
from laiive_shared import EventDraft
from loguru import logger
from openai import OpenAI

from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

EXTRACTION_PROMPT_VERSION = "v2"

EXTRACTION_PROMPT = """Extract live music event information from this text. Today is {today}.

Return ONE JSON object with ONLY the fields you can actually identify:
{{
  "name": string,            // event title if stated (do NOT invent one)
  "artists": [string, ...],  // performing artists/bands/DJs
  "start_at": "YYYY-MM-DDTHH:MM:SS",  // resolve relative dates using today's date
  "venue": string,
  "address": string,         // street address if stated
  "city": string,
  "venue_type": "club" | "bar" | "concert_hall" | "arena" | "festival_site" | "open_air" | "other",
  "price_min": number,       // 0 for free events
  "price_max": number,       // only when a range is stated
  "price_currency": string,  // ISO code (EUR, USD...) only when stated or implied by symbol
  "description": string,     // short description in the text's own words
  "genre": string,           // lowercase-hyphenated slug, e.g. "indie-rock"
  "ticket_url": string
}}

Rules:
- Omit any field that is not present. NEVER invent data.
- Numbers for prices — no currency symbols.
- JSON only. No explanation, no markdown fences.

Text to extract from:
{text}"""


def extract_draft_from_text(text: str) -> EventDraft:
    """LLM extraction of a (possibly partial) EventDraft from free text."""
    response = _client.chat.completions.create(
        model=settings.conversation_model,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    today=date.today().isoformat(), text=text
                ),
            }
        ],
        temperature=0.0,
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse extraction response: {content[:200]}")
        return EventDraft()
    if not isinstance(data, dict):
        return EventDraft()

    if isinstance(data.get("artists"), str):
        data["artists"] = [data["artists"]]
    for price_key in ("price_min", "price_max"):
        value = data.get(price_key)
        if isinstance(value, str):
            cleaned = value.lower().strip().replace(",", ".")
            if cleaned in ("free", "gratis", "0", ""):
                data[price_key] = 0.0
            else:
                try:
                    data[price_key] = float(cleaned)
                except ValueError:
                    data.pop(price_key)

    known = {k: v for k, v in data.items() if k in EventDraft.model_fields and v}
    if data.get("price_min") == 0:
        known["price_min"] = 0.0  # free is a real value, don't drop it
    try:
        return EventDraft(**known)
    except Exception as e:
        logger.warning(f"Extraction produced an invalid draft: {e}")
        return EventDraft()


def audio_to_text(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using OpenAI Whisper."""
    response = _client.audio.transcriptions.create(
        model=settings.whisper_model,
        file=(filename, audio_bytes),
    )
    return response.text


def image_to_text(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Describe event information found in an image (poster, flyer, ...)."""
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
                            "Include: event name, artist names, date and time, venue, "
                            "address, city, price, description, genre, and ticket URL "
                            "if visible. Return the information as plain text."
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
    """Extract text from a document."""
    if filename.lower().endswith((".txt", ".csv", ".md")):
        return doc_bytes.decode("utf-8", errors="replace")
    return image_to_text(doc_bytes, mime_type="application/pdf")


def extract_from_url(url: str, language: str = "en") -> EventDraft:
    """Fetch a URL and extract an EventDraft from its content."""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as http:
            resp = http.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; laiive-bot/1.0)"},
            )
            resp.raise_for_status()
            page_text = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        raise ValueError(f"Could not fetch URL: {e}")

    max_chars = 8000
    if len(page_text) > max_chars:
        page_text = page_text[:max_chars]

    return extract_draft_from_text(
        f"Webpage content (language preference: {language}):\n{page_text}"
    )
