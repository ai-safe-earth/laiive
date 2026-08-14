"""Contract test: the TS mirror must carry exactly the pydantic model fields."""

import re
from pathlib import Path

import pytest

from laiive_shared import cards, protocol

TS_SOURCE = (Path(__file__).parent.parent / "ts" / "protocol.ts").read_text(
    encoding="utf-8"
)

MIRRORED_MODELS = [
    cards.EventCard,
    cards.EventDraft,
    protocol.MessageDelta,
    protocol.EventsResult,
    protocol.FormExtracted,
    protocol.Status,
    protocol.Error,
    protocol.Done,
]


def ts_interface_fields(name: str) -> set[str]:
    match = re.search(
        rf"export interface {name} \{{(.*?)\}}", TS_SOURCE, flags=re.DOTALL
    )
    assert match, f"interface {name} missing from ts/protocol.ts"
    return {
        m.group(1)
        for m in re.finditer(r"^\s*(\w+)\??:", match.group(1), flags=re.MULTILINE)
    }


@pytest.mark.parametrize("model", MIRRORED_MODELS, ids=lambda m: m.__name__)
def test_ts_mirror_matches_pydantic(model):
    assert ts_interface_fields(model.__name__) == set(model.model_fields)


def test_ts_event_names_match():
    match = re.search(r"SSE_EVENTS = \[(.*?)\]", TS_SOURCE, flags=re.DOTALL)
    ts_events = set(re.findall(r'"([^"]+)"', match.group(1)))
    py_events = {
        m.event
        for m in MIRRORED_MODELS
        if hasattr(m, "event") and isinstance(getattr(m, "event", None), str)
    }
    assert ts_events == py_events
