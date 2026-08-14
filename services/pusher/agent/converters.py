"""Convert voice, image, URL, and text inputs into an EventDraft.

The one extraction prompt for every modality (04-plan: the duplicated
prompts/functions merged here). Everything funnels into `EventDraft`.
"""

import base64
import io
import json
from datetime import date

import httpx
from laiive_shared import EventDraft, transcribe
from loguru import logger
from openai import OpenAI

from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

EXTRACTION_PROMPT_VERSION = "v3"

EXTRACTION_PROMPT = """Extract live music events from this text. Today is {today}.

The text may describe ONE event or MANY — a spreadsheet of gigs, a festival
line-up, a promoter listing their season. Return every event you find.

Return JSON of the form {{"events": [ ... ]}}, where each entry carries ONLY
the fields you can actually identify:
{{
  "name": string,            // event title if stated (do NOT invent one)
  "artists": [string, ...],  // performing artists/bands/DJs
  "start_at": "YYYY-MM-DDTHH:MM:SS",  // resolve relative dates using today's date
  "venue": string,
  "address": string,         // street address if stated
  "city": string,
  "venue_type": "club" | "bar" | "concert_hall" | "arena" | "festival_site" | "open_air" | "other",  // only when the text says so — omit rather than guessing "other"
  "price_min": number,       // 0 for free events
  "price_max": number,       // only when a range is stated
  "price_currency": string,  // ISO code (EUR, USD...) only when stated or implied by symbol
  "description": string,     // short description in the text's own words
  "genre": string,           // lowercase-hyphenated slug, e.g. "indie-rock"
  "ticket_url": string
}}

Rules:
- One entry per event; a single event is a list of one.
- Keep the events in the order they appear in the text, and keep that order
  stable — the same text must always produce the same events in the same
  order, because the promoter refers to them by position ("the third one").
- A detail stated once for the whole set ("all of these are at Sala Clamores")
  belongs on every event it covers.
- Omit any field that is not present. NEVER invent data.
- Numbers for prices — no currency symbols.
- JSON only. No explanation, no markdown fences.

Text to extract from:
{text}"""


def extract_drafts_from_text(text: str) -> list[EventDraft]:
    """LLM extraction of every event described in free text.

    One extraction path whether the promoter sent one gig or fifty: the whole
    conversation is re-read every turn, so a later sentence ("all of them are
    at Sala Clamores", "the third one starts at 21:00") lands on the right
    drafts without any merge rules on either side of the wire.
    """
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
        return []

    drafts = [
        draft
        for entry in _entries(data)
        if (draft := _entry_to_draft(entry)) is not None
    ]
    if len(drafts) > 1:
        logger.info(f"Extraction recognized {len(drafts)} events")
    return drafts


def _entries(data: object) -> list[dict]:
    """The event list, however the model chose to wrap it.

    Asked for `{"events": [...]}` it usually complies, but a lone event often
    comes back as a bare object and sometimes as a bare list — all three are
    the same thing to us.
    """
    if isinstance(data, dict):
        events = data.get("events")
        if isinstance(events, list):
            return [e for e in events if isinstance(e, dict)]
        return [data]
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    return []


def _entry_to_draft(entry: dict) -> EventDraft | None:
    data = dict(entry)

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
        return None


def extract_draft_from_text(text: str) -> EventDraft:
    """First event only — for the single-draft endpoints 4c deletes."""
    drafts = extract_drafts_from_text(text)
    return drafts[0] if drafts else EventDraft()


def audio_to_text(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using OpenAI Whisper (shared with the retriever)."""
    return transcribe(_client, audio_bytes, filename, settings.whisper_model)


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


class UnreadableDocument(ValueError):
    """The document carries no text we can extract."""


def document_to_text(doc_bytes: bytes, filename: str) -> str:
    """Extract text from a document (PDF, DOCX, or plain text).

    PDFs are read through their text layer. A scanned flyer has none, and
    OCR-ing it would mean rendering pages to images (pymupdf, ~40 MB of
    dependency) — the vision path already handles flyers well, so we ask for
    the image instead of carrying the renderer.
    """
    name = filename.lower()

    if name.endswith((".txt", ".csv", ".md", ".json")):
        return doc_bytes.decode("utf-8", errors="replace")

    if name.endswith(".pdf"):
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(doc_bytes))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            # A file the user picked badly is their problem to fix, not a 5xx.
            logger.warning(f"Could not parse PDF {filename}: {e}")
            raise UnreadableDocument(
                "Could not read that PDF. Send the flyer as an image instead."
            ) from e
        if not text.strip():
            raise UnreadableDocument(
                "This PDF has no text layer (it looks scanned). "
                "Send the flyer as an image instead."
            )
        return text.strip()

    if name.endswith(".docx"):
        from docx import Document

        try:
            document = Document(io.BytesIO(doc_bytes))
        except Exception as e:
            logger.warning(f"Could not parse DOCX {filename}: {e}")
            raise UnreadableDocument("Could not read that document.") from e
        return "\n".join(p.text for p in document.paragraphs).strip()

    raise UnreadableDocument(
        f"Unsupported document type: {filename}. Send a PDF, DOCX, TXT, or an image."
    )


URL_MAX_CHARS = 8000


def url_to_text(url: str) -> str:
    """Fetch a page and return its content as text, truncated to a sane size."""
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
        raise ValueError(f"Could not fetch URL: {e}") from e

    return page_text[:URL_MAX_CHARS]


def extract_from_url(url: str, language: str = "en") -> EventDraft:
    """Fetch a URL and extract an EventDraft from its content."""
    page_text = url_to_text(url)
    return extract_draft_from_text(
        f"Webpage content (language preference: {language}):\n{page_text}"
    )
