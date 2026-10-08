"""The correlation id a service adopts from the gateway.

One function, shared, because the last time this contract lived in a single
service it silently stopped being a contract. The retriever was changed in eval
phase 0 to read the gateway's ``x-request-id`` so its ``eval_records`` row would
join the gateway's ``conversation_logs`` row; the pusher was not in that change
and kept minting its own uuid. The result was two ids per pusher turn — the
gateway's in Supabase, the pusher's in its own logs and its ``done`` frame — and
nothing joining them.

Why the header is trustworthy: the gateway deletes any client-sent copy before
injecting its own (``services/gateway/src/proxy.ts``), alongside ``x-user-id``
and ``x-internal-key``. A client therefore cannot choose the id under which its
turn is recorded, which is what stops one caller writing telemetry that
impersonates another's.

The fallback is for direct calls that never crossed the gateway — tests, and a
curl straight at 8002/8003. Those get a locally minted id that joins nothing,
which is the correct degradation: a row that is honestly orphaned beats a row
that is wrong.
"""

import uuid

from fastapi import Request

HEADER = "x-request-id"


def request_id_from(raw: Request) -> str:
    """The gateway's id if it sent one, else a fresh uuid4."""
    return raw.headers.get(HEADER) or str(uuid.uuid4())
