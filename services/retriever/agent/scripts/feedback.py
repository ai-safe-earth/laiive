"""Weekly read of real-user feedback, grouped into threads instead of single logs.

Reads three Supabase tables (GET only, service role) joined on request_id:
conversation_logs (the question), eval_records (the answer) and turn_feedback
(the thumbs). Picks the turns worth reading: every thumb, plus the failures
nobody complained about (no events found, or an error). Hard facts are labelled
in code; one LLM call then sorts the turns into named threads, reusing the
names in evals/failure_modes.json so a thread can be followed week to week.

Prints locally only. The grouping call sends questions and reasons to OpenAI, the
same provider the chat already uses; nowhere else. The saved file holds thread
names, descriptions and counts, nothing a user typed.

Run: cd services/retriever && uv run --no-sync python -m agent.scripts.feedback [--days 7]
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from config import settings

from ..utils.llm_utils import get_openai_client

MODES_FILE = Path(__file__).resolve().parents[2] / "evals" / "failure_modes.json"
CHAT_ROUTES = {"/api/chat/stream", "/api/chat"}

THREAD_PROMPT = """You group chat turns from a live-music events assistant into threads:
recurring lines of failure (for thumbs-down and unflagged failures) or of success
(for thumbs-up). Each turn has an id, its signals, the user's question, the
assistant's answer when known, and the user's typed reason when given.

Known threads (reuse these names whenever one fits):
{known}

Return JSON only:
{{"threads": [{{"name": "short-kebab-name", "kind": "failure" | "success",
  "description": "one sentence: what goes wrong (or right), in general terms"}}],
 "turns": {{"<turn id>": "<thread name>", ...}}}}
"turns" has one entry for EVERY turn id you were given, each naming a listed thread.

Rules:
- Every turn id in exactly one thread.
- Group by WHAT WOULD FIX IT, not by the symptom. "no-events" is a symptom: split it
  by likely cause read from the question and answer (a city or town we have no events
  for, a date window too narrow, a genre missing, a short follow-up that lost the
  context, the database being down, ...). Split complaints by what the reason says
  went wrong (duplicates, wrong event name, missing event, follow-up repeats results,
  ...).
- Aim for 4 to 10 threads of at least 2 turns; a one-off goes in the closest thread.
- A new thread only when no known one fits.
- A thumbs-down turn is never in a success thread.
- Descriptions are general and never quote a user."""


def _get(table: str, select: str, since: str) -> list[dict]:
    base = settings.supabase_url.rstrip("/") + "/rest/v1/"
    key = settings.supabase_service_role_key
    out: list[dict] = []
    while True:
        r = httpx.get(
            f"{base}{table}?select={select}&created_at=gte.{since}&order=created_at",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range": f"{len(out)}-{len(out) + 999}",
            },
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        out += batch
        if len(batch) < 1000:
            return out


def _short(text: str | None, n: int = 280) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def build_turns(
    logs: list[dict], records: list[dict], feedback: list[dict]
) -> list[dict]:
    """One dict per chat turn, with the answer and the thumbs attached when known."""
    answers = {r["request_id"]: r for r in records}
    thumbs: dict[str, dict] = defaultdict(lambda: {"rating": None, "reason": None})
    for f in feedback:
        t = thumbs[f["request_id"]]
        t["rating"] = f.get("rating") or t["rating"]
        t["reason"] = f.get("reason") or t["reason"]
    chats = [
        (log, (log.get("payload") or {}).get("messages") or [])
        for log in logs
        if log["route"] in CHAT_ROUTES
    ]

    def replied(messages: list[dict]) -> str | None:
        """The answer as the next turn of the same chat resent it in its history.

        Answers were captured only from 2026-08-26, and most thumbs are older.
        ponytail: O(n^2) over chat turns; index by first message if it grows.
        """
        n = len(messages)
        for _, later in chats:
            if len(later) > n and later[:n] == messages:
                if later[n].get("role") == "assistant":
                    return later[n].get("content")
        return None

    turns = []
    for log, messages in chats:
        payload = log.get("payload") or {}
        users = [m for m in messages if m.get("role") == "user"]
        rid = log["request_id"]
        rec = answers.get(rid)
        turns.append(
            {
                "id": rid,
                "at": log["created_at"][:16],
                "question": _short(users[-1]["content"] if users else ""),
                "earlier_turns": len(users) - 1 if users else 0,
                "has_location": bool(payload.get("location")),
                "status": log.get("status"),
                "answer": _short(rec["final_text"] if rec else replied(messages))
                or None,
                "query_type": rec["query_type"] if rec else None,
                "events": rec["row_count"] if rec else None,
                "errors": (rec["errors"] or []) if rec else [],
                **thumbs.get(rid, {"rating": None, "reason": None}),
            }
        )
    return turns


def signals(turn: dict) -> list[str]:
    """Facts that need no model."""
    out = []
    errors = " ".join(turn["errors"]).lower()
    if "unavailable" in errors or "sessionexpired" in errors or "resolve" in errors:
        out.append("graph-down")
    elif turn["errors"]:
        out.append("error")
    if turn["status"] and turn["status"] >= 400:
        out.append(f"http-{turn['status']}")
    if turn["query_type"] == "event_search" and not turn["events"]:
        out.append("no-events")
    if turn["answer"] is None:
        out.append("answer-not-recorded")
    return out


def worth_reading(turn: dict) -> bool:
    return (
        bool(turn["rating"])
        or any(s in signals(turn) for s in ("graph-down", "error", "no-events"))
        or bool(turn["status"] and turn["status"] >= 400)
    )


def group(turns: list[dict], known: dict, model: str, focus: str = "") -> list[dict]:
    items = [
        {
            "id": i,
            "thumb": t["rating"] or "none",
            "signals": signals(t),
            "question": t["question"],
            "follow_up": t["earlier_turns"] > 0,
            "answer": t["answer"],
            "reason": t["reason"],
        }
        for i, t in enumerate(turns)
    ]
    known_text = (
        "\n".join(
            f"- {name} ({m['kind']}): {m['description']}" for name, m in known.items()
        )
        or "(none yet)"
    )
    response = get_openai_client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": THREAD_PROMPT.format(known=known_text) + focus,
            },
            {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ],
    )
    out = json.loads(response.choices[0].message.content)
    return assign(out.get("threads", []), out.get("turns", {}), len(turns))


def split_big(
    threads: list[dict], turns: list[dict], known: dict, model: str
) -> list[dict]:
    """A failure thread holding over a quarter of the turns is a symptom, not a
    line of work: one more call splits it by cause into "parent/child" threads."""
    out = []
    for th in threads:
        if th["kind"] != "failure" or len(th["ids"]) < max(6, len(turns) / 4):
            out.append(th)
            continue
        prefix = th["name"] + "/"
        children = {
            k[len(prefix) :]: v for k, v in known.items() if k.startswith(prefix)
        }
        focus = (
            f"\n\nAll these turns share the thread '{th['name']}'. Split them by cause "
            "into 2 to 6 threads; never reuse that name. A cause is something to fix "
            "(no coverage for a place, a near-me radius too small, a date window too "
            "narrow, a follow-up that lost its context, a genre filter too strict), "
            "never a city name on its own."
        )
        for sub in group([turns[i] for i in th["ids"]], children, model, focus):
            sub["name"] = prefix + sub["name"]
            sub["ids"] = [th["ids"][i] for i in sub["ids"]]
            out.append(sub)
    return out


def assign(threads: list[dict], labels: dict, count: int) -> list[dict]:
    """Every turn in exactly one thread; what the model skipped is "unsorted"."""
    by_name = {th["name"]: {**th, "ids": []} for th in threads}
    unsorted = {"name": "unsorted", "kind": "failure", "ids": []}
    unsorted["description"] = "the model left these out or named no listed thread"
    for i in range(count):
        by_name.get(labels.get(str(i)), unsorted)["ids"].append(i)
    return [th for th in [*by_name.values(), unsorted] if th["ids"]]


def report(threads: list[dict], turns: list[dict], known: dict) -> str:
    total = len(turns)
    lines = []
    for kind in ("failure", "success"):
        rows = sorted(
            (th for th in threads if th["kind"] == kind), key=lambda th: -len(th["ids"])
        )
        if not rows:
            continue
        lines.append(f"\n######## {kind.upper()} THREADS")
        for th in rows:
            n = len(th["ids"])
            before = known.get(th["name"], {}).get("last_count")
            trend = "new" if before is None else f"{n - before:+d} vs last run"
            members = [turns[i] for i in th["ids"]]
            downs = sum(t["rating"] == "down" for t in members)
            lines.append(
                f"\n== {th['name']}  {n} turns ({n / total:.0%})  {downs} thumbs-down  [{trend}]"
            )
            lines.append(f"   {th['description']}")
            for t in members[:3]:
                why = f"  | reason: {t['reason']}" if t["reason"] else ""
                shown = [s for s in signals(t) if s != "answer-not-recorded"]
                lines.append(f'   - "{_short(t["question"], 120)}"  {shown}{why}')
            lines.append("   ids: " + " ".join(t["id"] for t in members))
    return "\n".join(lines)


def remember(threads: list[dict], known: dict, run_at: str) -> dict:
    """Thread names, descriptions and counts only: nothing a user typed."""
    for name in known:
        known[name]["last_count"] = 0
    for th in threads:
        entry = known.setdefault(
            th["name"], {"kind": th["kind"], "description": th["description"]}
        )
        entry["last_count"] = len(th["ids"])
        entry["last_run"] = run_at
    return dict(sorted(known.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--days", type=int, default=0, help="only the last N days (0: all)"
    )
    parser.add_argument("--model", default=settings.composer_model)
    parser.add_argument(
        "--no-save", action="store_true", help="do not update failure_modes.json"
    )
    args = parser.parse_args()

    since = (
        (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
        if args.days
        else "1970-01-01T00:00:00Z"
    ).replace("+00:00", "Z")
    turns = build_turns(
        _get("conversation_logs", "request_id,route,status,payload,created_at", since),
        _get(
            "eval_records", "request_id,final_text,query_type,row_count,errors", since
        ),
        _get("turn_feedback", "request_id,rating,reason", since),
    )
    picked = [t for t in turns if worth_reading(t)]
    # A request logged with no question (refused at login or validation, or a
    # payload without messages) has nothing to read: count it, no model needed.
    blank = [t for t in picked if not t["question"]]
    picked = [t for t in picked if t["question"]]
    if blank:
        codes = sorted({str(t["status"]) for t in blank})
        print(
            f"{len(blank)} requests carried no question (status {', '.join(codes)}): "
            "login or payload problems, not answers"
        )
    ups = sum(t["rating"] == "up" for t in picked)
    downs = sum(t["rating"] == "down" for t in picked)
    print(
        f"{len(turns)} chat turns; reading {len(picked)}: {downs} down, {ups} up, "
        f"{len(picked) - ups - downs} unflagged failures"
    )
    if not picked:
        return

    known = (
        json.loads(MODES_FILE.read_text(encoding="utf-8"))
        if MODES_FILE.exists()
        else {}
    )
    threads = split_big(group(picked, known, args.model), picked, known, args.model)
    print(report(threads, picked, known))
    if not args.no_save:
        run_at = datetime.now(timezone.utc).date().isoformat()
        MODES_FILE.write_text(
            json.dumps(remember(threads, known, run_at), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(f"\nthread names and counts saved to {MODES_FILE.name}")


if __name__ == "__main__":
    main()
