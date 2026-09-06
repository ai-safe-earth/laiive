# Applying controls in any language

Language-neutral shapes for when no `apply/<language>.md` matches (Java, Rust, C#, Ruby,
shell, config-only repos). Each is a pattern, not a library; translate it into the idiom the
codebase already uses and cite only APIs you have checked.

## Allowlist (AUD-103, AUD-104, AUD-401, AUD-405)

The model chooses a NAME; the code owns the mapping from name to action.

    ALLOWED = {"search": run_search, "read_ticket": read_ticket}
    fn = ALLOWED.get(name) or deny()

For URLs: parse, then compare scheme and host against a fixed set; refuse everything else;
no redirects to private ranges; timeout and byte cap on the response. For commands: an argv
array and a fixed executable, never a shell string. Default deny; the list grows by review.

## Approval gate (AUD-201, AUD-202)

    if name in REQUIRES_APPROVAL:
        decision = wait_for_human(name, args, timeout)   # may return "no" or time out
        if decision is not "yes": deny()

Properties that make it a gate rather than decoration: it can deny, a timeout is a denial,
the decision and who made it are logged (below), and it sits on the only path to the action.
A stub that returns "yes" is AUD-202.

## Dry run (AUD-203)

Every irreversible tool takes `dry_run` (default true in development) and returns the
planned effect -- recipients, rows, amount, path -- without performing it. The agent loop
calls with `dry_run=true` first, shows the plan at the gate, then calls for real.

## Idempotency key (AUD-203)

Each external write carries a key derived from the intent (`sha256(session, tool, args)`),
sent as `Idempotency-Key` or stored before the call. A retried loop or a duplicated message
then cannot send twice or charge twice.

## Iteration cap and deadline (AUD-102)

A named constant checked at the top of every loop iteration, plus a wall-clock deadline
passed into every call. Exceeding either is an error the caller sees, not a silent stop.

## Session budget (AUD-105)

A counter per session incremented before every tool dispatch and compared against a named
maximum; a per-tool counter for the expensive or irreversible ones.

## Kill switch (AUD-107)

One environment variable (`AGENT_DISABLED=1`) or one settings field read AT RUNTIME at the
top of every request or loop iteration. When set: refuse new work, finish or abort the
current step, log that the switch was honoured. A declaration in a settings class, a
`.env.example` line or a comment is not a kill switch; the audit checks for a read.

## Audit log shape (AUD-702, AUD-504)

Append-only, one record per tool call, written before the action and completed after:

    {"ts": "2026-09-02T09:12:00Z", "session": "s-123", "user": "u-45",
     "tool": "send_email", "args_sha256": "...", "decision": "approved",
     "approver": "alice", "outcome": "ok", "duration_ms": 412}

Hashes and lengths for prompts and responses, never their text (AUD-504). The file or sink
is one the application cannot truncate.

## Trust-boundary split (AUD-301)

Two processes or two agents: one that can read private data and cannot act externally;
one that can act externally and never sees raw private data or raw untrusted content.
Between them, a validated structure (a schema with fixed fields), not free text. Untrusted
content (web pages, tickets, emails, MCP results from servers outside `--trusted-mcp-hosts`)
is summarised in its own model call whose output is treated as data.

## Secrets and PII (AUD-501, AUD-502, AUD-503, AUD-106)

Values live in the environment or a secrets manager; config references a variable name.
The agent process gets a scoped credential. Nothing that matches a key pattern is bound
into prompt text; a committed key is rotated, not just deleted from history.

## Supply chain (AUD-602, AUD-605, AUD-606)

Every install line, MCP server and container image is pinned to a version or digest; weights
are pinned by revision; a dependency scanner runs in CI and its report is what turns AUD-606
from UNKNOWN into MEASURED.

## Observability (AUD-701)

Traces that record the model id, prompt and response hashes, tool calls and their decisions
-- OpenTelemetry GenAI attributes or an LLM-specific tracer. Generic APM alone is
`AUD-701/apm-only`.

## Incident path and governance (AUD-703, AUD-1001, AUD-1002)

A `SECURITY.md` with a contact and a response window; a system card (`aisg init --defaults`
writes one) naming purpose, data, models and incident contact. The risk tier on it is the
operator's legal determination; leave `unknown` in place rather than guessing, and say so.

## Evals (AUD-901, AUD-904)

A committed corpus with attack AND benign cases, run in CI with a threshold that fails the
build. `aisg measure` does this for pipelines built with this package; promptfoo, deepeval,
inspect_ai, garak and pyrit cover other shapes. Attacks alone reward a guard that blocks
everything.
