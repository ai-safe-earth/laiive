"""Conversational event extraction — collects required fields from the user."""

import json
import threading
from typing import Optional
from openai import OpenAI
from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

REQUIRED_FIELDS = ["artist", "date_time", "venue", "city", "price"]
OPTIONAL_FIELDS = ["description", "genre", "ticket_url"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# City → currency (covers major markets, defaults to EUR)
CITY_CURRENCY = {
    "new york": "USD",
    "los angeles": "USD",
    "chicago": "USD",
    "san francisco": "USD",
    "austin": "USD",
    "nashville": "USD",
    "miami": "USD",
    "seattle": "USD",
    "boston": "USD",
    "denver": "USD",
    "london": "GBP",
    "manchester": "GBP",
    "birmingham": "GBP",
    "glasgow": "GBP",
    "edinburgh": "GBP",
    "bristol": "GBP",
    "tokyo": "JPY",
    "osaka": "JPY",
    "toronto": "CAD",
    "montreal": "CAD",
    "vancouver": "CAD",
    "sydney": "AUD",
    "melbourne": "AUD",
    "mexico city": "MXN",
    "guadalajara": "MXN",
    "bogota": "COP",
    "medellin": "COP",
    "buenos aires": "ARS",
    "sao paulo": "BRL",
    "rio de janeiro": "BRL",
    "santiago": "CLP",
    "lima": "PEN",
    "zurich": "CHF",
    "geneva": "CHF",
    "basel": "CHF",
    "copenhagen": "DKK",
    "stockholm": "SEK",
    "gothenburg": "SEK",
    "oslo": "NOK",
    "warsaw": "PLN",
    "krakow": "PLN",
    "prague": "CZK",
    "budapest": "HUF",
    "bucharest": "RON",
    "istanbul": "TRY",
    "seoul": "KRW",
    "bangkok": "THB",
    "mumbai": "INR",
    "delhi": "INR",
    "bangalore": "INR",
    "singapore": "SGD",
    "beijing": "CNY",
    "shanghai": "CNY",
}

SYSTEM_PROMPT = """You are an assistant that helps users submit live music events to a database.

Your job is to collect event information through conversation. You need these REQUIRED fields:
- **artist**: Artist or band name
- **date_time**: Date and time of the event (e.g. "2026-03-20 at 21:00")
- **venue**: Venue name
- **city**: City where the venue is located
- **price**: Ticket price (number only, currency is auto-detected from city)

These fields are OPTIONAL (accept if offered, don't insist):
- **description**: Short description of the event
- **genre**: Music genre (e.g. jazz, rock, electronic, hip-hop)
- **ticket_url**: URL to buy tickets

## Current state of collected fields:
{fields_state}

## Rules:
- If the user provides information (even partial), acknowledge it and ask for what's still missing.
- If the user provides info via a converted image/voice/doc, extract as many fields as you can from it.
- Be concise and friendly. Ask for ONE or TWO missing fields at a time, not all at once.
- When ALL required fields are collected, summarize the event and ask the user to confirm with "yes" or "confirm".
- If the user confirms, respond with EXACTLY: **CONFIRMED**
- Reply in the same language as the user.
- Never invent data. Only use what the user provides."""

EXTRACTION_PROMPT = """Extract event information from this text. Return a JSON object with ONLY the fields you can identify.

Possible fields: artist, date_time, venue, city, price, description, genre, ticket_url

Rules:
- artist: artist or band name (string)
- date_time: date and time in ISO-like format "YYYY-MM-DD HH:MM" or natural language
- venue: venue name (string)
- city: city name (string)
- price: numeric value only, no currency symbol (number or string like "25" or "free")
- description: short event description (string)
- genre: music genre slug (string, lowercase, e.g. "jazz", "electronic")
- ticket_url: URL string

Return ONLY a valid JSON object. No explanation, no markdown fences.

Text to extract from:
{text}"""


class Session:
    """In-memory conversation session for event submission."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.fields: dict[str, Optional[str]] = {f: None for f in ALL_FIELDS}
        self.history: list[dict[str, str]] = []
        self.confirmed = False

    def _fields_state(self) -> str:
        lines = []
        for f in ALL_FIELDS:
            val = self.fields[f]
            required = f in REQUIRED_FIELDS
            tag = "REQUIRED" if required else "optional"
            status = f"'{val}'" if val else "MISSING" if required else "not provided"
            lines.append(f"- {f} [{tag}]: {status}")
        return "\n".join(lines)

    def _missing_required(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if not self.fields[f]]

    def all_required_collected(self) -> bool:
        return len(self._missing_required()) == 0

    def extract_fields_from_text(self, text: str) -> dict:
        """Use LLM to extract fields from unstructured text."""
        response = _client.chat.completions.create(
            model=settings.conversation_model,
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT.format(text=text)},
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )
        try:
            extracted = json.loads(content)
        except json.JSONDecodeError:
            return {}

        if not isinstance(extracted, dict):
            return {}

        # Merge extracted fields (don't overwrite existing with empty)
        for key, value in extracted.items():
            if key in ALL_FIELDS and value:
                self.fields[key] = str(value)

        return extracted

    def chat(self, user_message: str) -> str:
        """Process a user message and return the assistant response."""
        # Try to extract fields from the message
        self.extract_fields_from_text(user_message)

        # Check if user is confirming
        if self.all_required_collected() and user_message.strip().lower() in (
            "yes",
            "confirm",
            "si",
            "sí",
            "ok",
            "lgtm",
            "confirmed",
            "dale",
            "ja",
        ):
            self.confirmed = True
            return "**CONFIRMED**"

        # Build conversation
        system = SYSTEM_PROMPT.format(fields_state=self._fields_state())
        messages = [{"role": "system", "content": system}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        response = _client.chat.completions.create(
            model=settings.conversation_model,
            messages=messages,
            temperature=0.5,
        )
        assistant_reply = response.choices[0].message.content.strip()

        # Track history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": assistant_reply})

        # Check if the LLM itself confirmed
        if "**CONFIRMED**" in assistant_reply:
            self.confirmed = True

        return assistant_reply

    def get_currency(self) -> str:
        """Auto-detect currency from city."""
        city = (self.fields.get("city") or "").lower().strip()
        return CITY_CURRENCY.get(city, "EUR")

    def to_event_data(self) -> dict:
        """Convert collected fields to the event structure for Neo4j."""
        price_raw = self.fields.get("price", "0")
        try:
            price_amount = float(str(price_raw).replace(",", "."))
        except (ValueError, TypeError):
            price_amount = 0.0

        return {
            "artist": self.fields["artist"],
            "event_name": self.fields.get("description")
            or f"{self.fields['artist']} Live",
            "date_time": self.fields["date_time"],
            "venue": self.fields["venue"],
            "city": self.fields["city"],
            "price_amount": price_amount,
            "price_currency": self.get_currency(),
            "description": self.fields.get("description") or "",
            "genre": self.fields.get("genre") or "",
            "ticket_url": self.fields.get("ticket_url") or "",
        }


class SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str) -> Session:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = Session(session_id)
            return self._sessions[session_id]

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


sessions = SessionStore()
