"""Coerce LLM extraction JSON into EventDrafts.

Every extractor (pusher conversation, search discovery) asks its model for
`{"events": [...]}` and gets back whatever the model felt like — a bare
object, a bare list, fenced markdown, string prices. The tolerance lives
here once so both services survive the same quirks.
"""

import logging

from .cards import EventDraft

logger = logging.getLogger(__name__)


def strip_fences(content: str) -> str:
    """Drop a ```json … ``` wrapper if the model added one."""
    if content.startswith("```"):
        lines = content.split("\n")
        return "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return content


def entries_from_json(data: object) -> list[dict]:
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


def entry_to_draft(entry: dict) -> EventDraft | None:
    """One extraction entry → EventDraft, or None when unusable."""
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
        logger.warning("Extraction produced an invalid draft: %s", e)
        return None
