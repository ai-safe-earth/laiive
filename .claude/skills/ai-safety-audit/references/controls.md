# Controls per audit rule

One section per `AUD` rule: the control to propose, its tier, and the control mapping the
finding carries. Use it in phase 3 together with `apply/<language>.md`.

How to read this file:

- **Tier**: T1 = a config or permission change; T2 = add a gate or a file; T3 = restructure
  code. Propose the cheapest tier that removes the blast radius, not the cheapest one that
  makes the finding go away.
- **Mapping**: `ASI` = OWASP Top 10 for Agentic Applications (ASI01 goal hijack, ASI02 tool
  misuse, ASI03 identity and privilege abuse, ASI04 supply chain, ASI05 unexpected code
  execution, ASI06 memory and context poisoning, ASI07 inter-agent communication, ASI08
  cascading failures, ASI09 human-agent trust, ASI10 rogue agents); `LLM` = OWASP Top 10 for
  LLM Applications 2025 (LLM01 prompt injection, LLM02 sensitive information disclosure,
  LLM03 supply chain, LLM04 data and model poisoning, LLM05 improper output handling, LLM06
  excessive agency, LLM07 system prompt leakage, LLM08 vector and embedding weaknesses,
  LLM09 misinformation, LLM10 unbounded consumption); `EU` = EU AI Act article; `NIST` = AI
  RMF function and subcategory. The `controls` field in the report is the authoritative
  tuple for the installed version; the tuples below were recorded when this file was
  written. They are evidence for a human reviewer. Never state or imply compliance with any
  of them, and never present a mapping as a verdict.
- **Detector vs gate**: a detector (prompt-injection guard, PII scanner, judge) lowers the
  probability that bad content passes; a gate (approval, allowlist, sandbox, budget) lowers
  the impact when it does. Never prescribe a detector as the sole control for a P1-P4 finding.
- Every rule is `[UNMEASURED]`. Say so.

## Alternatives table

The report's `recommendation.alternatives` names projects from this table. Say plainly when
one of them fits the codebase better than this package.

| project | what it gives you | what it does not cover |
|---|---|---|
| this package (`aisg`) | `ToolPolicyGuard` (per-role allow/deny, argument globs, approval callback, session budget), `PIIDetector` (redact / block / flag / tokenize with restore), `PromptInjectionGuard` (mention-vs-use aware), `RateLimiter`, `LLMToolFilter` (judge with a fail-closed high-risk list), `AuditLogger`, `TelemetryProvider`, YAML presets, `aisg measure` to score a pipeline against attack and benign corpora | sandboxing, host permission files, dependency vulnerabilities, package pinning, evals of the model itself |
| NeMo Guardrails | Colang flows for input, output, dialog and tool-call rails; a config directory the app loads; good when the conversation shape itself needs control | not a process sandbox, not a permission system; detectors and flows run in-process with the app |
| Guardrails AI | validators from a hub applied to inputs and outputs, structured-output validation, re-ask on failure | tool gating, budgets, host permissions |
| LLM Guard | input and output scanners (prompt injection, secrets, PII anonymise and de-anonymise, toxicity, banned topics, relevance) | gates; it is a scanner library and says so |
| Llama Guard | a classifier model over prompts and responses against a hazard taxonomy; runs behind an inference host | anything that is not a classification: no gating, no budgets, adds a model call per check; its own failure mode must be fail-closed for high-risk tools |

## P1 Blast radius

### AUD-101 Host permission over-grant (critical / medium / low)

- Control (T1): remove `Bash`, `Bash(*)` and shell-family wildcards from `permissions.allow`;
  list the exact commands instead. Remove `defaultMode: "bypassPermissions"`,
  `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, `yolo`, `autoAccept`,
  `--dangerously-skip-permissions` from CI and hooks. Sub-finding `/interpreter`
  (`Bash(python*)`, `Bash(npx*)`, ...): narrow to the scripts actually needed. Sub-finding
  `/docs`: a README that mentions the flag; usually no change.
- Rule 4 of SKILL.md applies: show the diff, wait for approval.
- Mapping: ASI03, ASI02, LLM06, EU:Art.14, NIST:GOVERN-1.7, NIST:MANAGE-2.2.

### AUD-102 Agent loop without an iteration cap (high)

- Control (T2): a named cap in the enclosing function (`max_iterations`, `max_turns`,
  `recursion_limit`, `deadline`) checked every iteration; a wall-clock deadline for loops
  that wait on tools.
- Mapping: ASI08, ASI10, LLM10, EU:Art.15, NIST:MANAGE-2.4, NIST:MEASURE-2.6.

### AUD-103 Fetch/browse tool without a URL allowlist (high)

- Control (T2): parse the URL, compare the host against an allowlist, refuse everything
  else; `ToolPolicy.argument_rules` with a `https://trusted.example/*` glob is the one-line
  form in this package. Add a size cap and a timeout on the fetch.
- Mapping: ASI01, ASI02, LLM01, LLM08, EU:Art.15, NIST:MAP-5.1, NIST:MANAGE-2.2.

### AUD-104 Exec tool without sandbox (critical)

- Control (T2): run the command inside a sandbox (container, gVisor, firejail, nsjail, a
  hosted sandbox such as e2b or modal) with no network by default and a read-only mount;
  never `shell=True`; argv only. If a sandbox is out of reach today, gate the tool
  (AUD-201) and say the sandbox is still owed.
- Mapping: ASI05, ASI02, LLM05, LLM06, EU:Art.15, NIST:MANAGE-2.2, NIST:MEASURE-2.7.

### AUD-105 No per-session tool budget (medium)

- Control (T2): `ToolPolicyGuard(max_tool_calls_per_session=N, max_calls_per_tool=M)`
  with one context dict reused across the session; or a counter in the agent state
  checked before every dispatch.
- Mapping: ASI08, ASI10, LLM10, LLM06, EU:Art.15, NIST:MANAGE-2.4.

### AUD-106 Broad credentials in agent scope (high)

- Control (T1): give the agent process its own scoped credential (read-only DB role,
  fine-grained token, a bucket-scoped key) and move broad ones out of its env. A finding with
  `gitignored: true` came from a developer machine's `.env`; say so.
- Rule 4 of SKILL.md applies.
- Mapping: ASI03, LLM02, LLM06, EU:Art.15, NIST:GOVERN-6.1, NIST:MANAGE-2.2.

### AUD-107 No kill switch (medium)

- Control (T2): one env var or settings field read at runtime at the top of every request
  or loop iteration (`AGENT_DISABLED`, `settings.kill_switch`) that stops dispatch when
  set. A declaration nobody reads does not count; sub-finding `/inert` means the target
  declares `GUARDRAILS_DISABLE_ALL`, which this package does not honour.
- Mapping: ASI10, ASI08, EU:Art.14, NIST:MANAGE-2.4, NIST:GOVERN-1.7.

### AUD-108 Unsafe hooks / CI supply (high)

- Control (T1): replace `curl ... | sh`, `npx -y <pkg>`, `pip install` from `http://` and
  `--trusted-host` with pinned, checksummed installs; keep hooks to commands the repo ships.
- Rule 4 of SKILL.md applies (CI workflows and host hook files).
- Mapping: ASI04, LLM03, EU:Art.15, NIST:GOVERN-6.1, NIST:MAP-4.1.

## P2 Irreversible-action gates

### AUD-201 Irreversible tool with no approval gate (critical)

- Control (T2): an approval step on the tool's call path: `ToolPolicyGuard(require_approval=
  [...], approval_callback=...)`, LangGraph `interrupt_before` with a checkpointer, an
  agent-framework `needs_approval` / `human_input` flag, or a queue a human drains. The gate
  must be able to say no; a callback that always returns true is AUD-202.
- Mapping: ASI02, ASI09, LLM06, EU:Art.14, NIST:MANAGE-2.2, NIST:GOVERN-1.7.

### AUD-202 Inert or bypassed gate (critical)

- Control (T2): supply the missing half: the `approval_callback` for `require_approval`, the
  `checkpointer` for `interrupt_before`; delete `auto_approve=True`,
  `human_in_the_loop=False`, `confirm=False` on destructive wrappers. `aisg measure` can show
  that the gate returns a decision; the audit cannot.
- Mapping: ASI02, ASI09, LLM06, EU:Art.14, NIST:MANAGE-2.2.

### AUD-203 No dry-run / idempotency on irreversible tool (medium)

- Control (T3): a `dry_run` parameter that returns the planned effect without performing it;
  an idempotency key on every external write so a retried loop cannot double-charge or
  double-send.
- Mapping: ASI02, ASI08, LLM06, EU:Art.15, NIST:MANAGE-2.2.

## P3 Trust-boundary separation

### AUD-301 LETHAL TRIFECTA (critical)

- Control (T3): split the scope so no single function or unit holds all three legs. Common
  splits: a reader agent with private data and no external action feeding a writer agent
  that sees only a structured, validated summary; untrusted content quarantined into a
  separate model call whose output is data, not instructions; every external action behind
  an approval gate (AUD-201) with `PIIDetector(action="tokenize")` in front of the model so
  private values never reach it in the first place.
- Mapping: ASI01, ASI02, ASI06, LLM01, LLM02, LLM06, EU:Art.9, EU:Art.15, NIST:MAP-5.1,
  NIST:MANAGE-2.2.

### AUD-302 Untrusted content concatenated into a prompt (high)

- Control (T2): delimit and label untrusted spans, put them in a user turn rather than the
  system prompt, run a sanitiser (`PromptInjectionGuard`, LLM Guard, Lakera, Rebuff) on the
  path, and keep instructions and data in separate message parts. A detector alone is not
  enough when the model can act (see AUD-201).
- Mapping: ASI01, ASI06, LLM01, EU:Art.15, NIST:MEASURE-2.7, NIST:MANAGE-2.2.

### AUD-303 System prompt built from request data (high)

- Control (T3): the system prompt is a constant; per-request values go into a user message
  or a structured field the model reads as data.
- Mapping: ASI01, LLM01, LLM07, EU:Art.15, NIST:MEASURE-2.7.

## P4 Output-sink taint

All six: the control is the same shape. Model output is data; it never becomes a command,
a query string, markup, a URL or a path without going through a validator that knows the
sink. A `match_kind: grep` finding is co-located and unverified; say so, then look at the
code before proposing a change.

### AUD-401 Model output -> shell (critical)

- Control (T3): no shell; argv arrays only (`subprocess.run([...])`, `execFile`,
  `exec.Command(name, args...)`); an allowlist of commands the model may name; a sandbox
  (AUD-104) around the rest.
- Mapping: ASI05, ASI02, LLM05, EU:Art.15, NIST:MEASURE-2.7, NIST:MANAGE-2.2.

### AUD-402 Model output -> eval / dynamic import (critical)

- Control (T3): remove `eval` / `exec` / `new Function` / `vm.runIn*` on model-derived
  strings; parse a structured format (`json.loads` into a schema) and dispatch by name from
  a fixed table.
- Mapping: ASI05, LLM05, EU:Art.15, NIST:MEASURE-2.7.

### AUD-403 Model output -> SQL (critical)

- Control (T3): parameterised queries only; a read-only role for the agent's connection;
  never format a model string into SQL text.
- Mapping: ASI02, ASI05, LLM05, LLM02, EU:Art.15, NIST:MEASURE-2.7.

### AUD-404 Model output -> HTML (high)

- Control (T3): escape by default (`html.escape`, auto-escaping templates, `html/template`,
  React text nodes) and sanitise the rare rich-text case (DOMPurify, bleach); never
  `innerHTML =`, `dangerouslySetInnerHTML`, `mark_safe(`, `template.HTML(` on model output.
- Mapping: LLM05, ASI05, EU:Art.15, NIST:MEASURE-2.7.

### AUD-405 Model output -> URL / request (high)

- Control (T3): parse, then allowlist the host (AUD-103); no redirects to private ranges;
  timeouts and size caps; the request is a tool with a gate when it writes.
- Mapping: ASI02, LLM05, LLM06, EU:Art.15, NIST:MEASURE-2.7.

### AUD-406 Model output -> filesystem path (high)

- Control (T3): resolve against a fixed base directory and reject anything outside it; write
  only under a work directory; no `shutil.rmtree` on model-derived paths.
- Mapping: ASI02, ASI05, LLM05, LLM06, EU:Art.15, NIST:MEASURE-2.7.

## P5 Secrets and PII

### AUD-501 Secret literal in source (critical)

- Control (T1): move the value to the environment or a secrets manager, rotate it (a
  committed key is compromised regardless of history rewriting), add a pre-commit secret
  scanner. A `bucket: measured` finding was corroborated by gitleaks or detect-secrets.
- Rule 4 of SKILL.md applies.
- Mapping: LLM02, ASI03, EU:Art.15, NIST:GOVERN-6.1, NIST:MEASURE-2.7.

### AUD-502 Secret in MCP / host config (critical)

- Control (T1): reference the variable (`"env": {"API_KEY": "${API_KEY}"}` or the host's
  own env passthrough) instead of the literal; rotate.
- Rule 4 of SKILL.md applies.
- Mapping: LLM02, ASI03, ASI04, EU:Art.15, NIST:GOVERN-6.1.

### AUD-503 Secret or PII bound into a prompt (high)

- Control (T2): `PIIDetector(action="tokenize")` on the input stage and restore on output;
  never bind `os.environ[...]` or a secrets-manager value into prompt text; pass credentials
  to tools out of band.
- Mapping: LLM02, LLM07, ASI03, EU:Art.10, EU:Art.15, NIST:MEASURE-2.10.

### AUD-504 Verbatim prompt/response logging (medium)

- Control (T2): log hashes and lengths (`AuditLogger(include_content_hash=True)`), or
  redact through `PIIDetector` before logging; never `print(response)` in production paths.
- Mapping: LLM02, EU:Art.10, EU:Art.12, NIST:MEASURE-2.10, NIST:GOVERN-1.4.

### AUD-505 Literal PII in prompts / fixtures / logs (medium)

- Control (T2): replace with placeholders (`user@example.com`, `555-01xx`, RFC 5737 IPs);
  delete committed log samples; scrub eval datasets. Snippets in the report are redacted.
- Mapping: LLM02, EU:Art.10, NIST:MEASURE-2.10, NIST:MAP-4.1.

## P6 Supply chain

### AUD-601 Unpinned model id (medium)

- Control (T1): a dated or versioned model id (`-2025-..`, a snapshot name, a digest tag),
  recorded in one place; `aisg measure` and `aisg probe` reports carry `models[]` so AUD-903
  can see a change.
- Mapping: LLM03, ASI04, EU:Art.15, NIST:GOVERN-6.1, NIST:MAP-4.1.

### AUD-602 Unpinned MCP server / bootstrap (high)

- Control (T1): `npx -y pkg@1.2.3`, `uvx --from 'pkg==1.2.3'`, `pip install 'pkg==1.2.3'`,
  `docker run image@sha256:...`; a lockfile for MCP servers where the host supports one.
- Mapping: ASI04, LLM03, EU:Art.15, NIST:GOVERN-6.1, NIST:MAP-4.1.

### AUD-603 Remote or plaintext MCP transport (high)

- Control (T1): loopback or `https://` with an authenticated endpoint; name known-good
  internal hosts with `--trusted-mcp-hosts` so they stop counting as untrusted.
- Mapping: ASI04, ASI07, LLM03, EU:Art.15, NIST:MEASURE-2.7.

### AUD-604 MCP tool-description poisoning (critical)

- Control (T1): remove the server or pin it to a reviewed version; treat tool descriptions
  as untrusted input the model reads on every turn. This rule is never downgraded as a
  "mention": a description that discusses an injection phrase still carries it into context.
- Mapping: ASI01, ASI04, ASI06, LLM01, LLM03, EU:Art.15, NIST:MAP-4.1.

### AUD-605 Unpinned weights / `trust_remote_code` (high)

- Control (T1): `revision=` on `from_pretrained` and `hf_hub_download`; drop
  `trust_remote_code=True` or vendor the code; `torch.load(..., weights_only=True)`; no
  `pickle.load` on model files.
- Mapping: LLM03, LLM04, ASI04, EU:Art.15, NIST:GOVERN-6.1.

### AUD-606 Dependency vulnerabilities (per tool)

- Control (T1): upgrade or pin as the scanner advises; this is the one rule that is
  `MEASURED` (pip-audit, npm audit, osv-scanner ran now). When it is UNKNOWN, the scanner
  was not on PATH; install it and rerun.
- Mapping: LLM03, ASI04, EU:Art.15, NIST:GOVERN-6.1, NIST:MANAGE-4.1.

## P7 Observability, audit log, incident path

### AUD-701 No observability on LLM calls (medium; `/apm-only` low)

- Control (T2): tracing that records prompts, tool calls and model ids: `TelemetryProvider`
  from this package (OTel GenAI attributes), Langfuse, LangSmith, Traceloop, Phoenix, Weave.
  Generic APM (Sentry, Datadog) does not satisfy the rule and yields `/apm-only`.
- Mapping: EU:Art.12, EU:Art.72, NIST:MEASURE-2.8, NIST:MANAGE-4.1, LLM06.

### AUD-702 No tool-call audit log (high)

- Control (T2): an append-only record per tool call (who, what, arguments hash, decision,
  outcome): `AuditLogger` attached to the pipeline, structlog, or the shape in
  `apply/generic.md`.
- Mapping: EU:Art.12, EU:Art.14, NIST:MEASURE-2.8, NIST:GOVERN-1.4, ASI02.

### AUD-703 No incident path (low)

- Control (T2): a `SECURITY.md` with a contact and a response window, an incident runbook,
  `incident_contact` on the system card.
- Mapping: EU:Art.73, NIST:GOVERN-4.3, NIST:MANAGE-4.1.

## P8 Detection guards

### AUD-801 Guard present but unmeasured (medium)

- Control (T2): run `aisg measure --config <pipeline.yaml>` (phase 5, with approval) or an
  equivalent eval, commit the report, and keep it newer than the guard config. A guard with
  no measurement is a claim.
- Mapping: NIST:MEASURE-1.1, NIST:MEASURE-2.5, EU:Art.15, LLM01.

### AUD-802 Guard configured fail-open (high)

- Control (T1): `fail_open: false`; no `except Exception: pass` around a guard call; for LLM
  judges, a fail-closed list for high-risk tools (`LLMToolFilter.high_risk_fail_closed`).
- Mapping: ASI08, LLM06, EU:Art.15, NIST:MANAGE-2.2, NIST:MEASURE-2.7.

### AUD-803 Reported guard below threshold (high, `REPORTED <age>`)

- Control (T1): retune or replace the guard named in `threshold_failures`, re-measure, or
  disable it and say what replaces it. The finding is as old as the report it came from.
- Mapping: NIST:MEASURE-2.5, NIST:MANAGE-2.2, EU:Art.15.

### AUD-804 LLM judge without credentials or timeout (medium)

- Control (T1): declare the key the judge needs, set a timeout, and decide what happens
  when it fails (fail-closed for high-risk tools). Without credentials the judge silently
  costs seconds per request and returns its fallback.
- Mapping: ASI08, LLM10, EU:Art.15, NIST:MANAGE-2.2.

### AUD-805 Keyword-only content filter (low)

- Control (T2): keep the list if it is cheap, but put a measured guard beside it
  (`PromptInjectionGuard`, a toxicity classifier, LLM Guard) and measure both.
- Mapping: LLM01, NIST:MEASURE-2.5, EU:Art.15.

## P9 Evaluation loop

### AUD-901 No evals in CI (high)

- Control (T2): a CI step that runs `aisg measure`, promptfoo, deepeval, inspect_ai, garak,
  pyrit or an equivalent against a committed corpus, with a threshold that fails the build.
- Mapping: NIST:MEASURE-2.5, NIST:MEASURE-2.7, EU:Art.9, EU:Art.15, LLM01.

### AUD-902 Probe report shows failed / inconclusive / errored / skipped cases (high / medium / low, `REPORTED <age>`)

- Control (T2): fix the guard for `failed`; rerun with a working endpoint for `errors`;
  add `--system-canary` for `skipped`; read the `inconclusive` cases by hand (the endpoint
  reflected the payload). Only `passed` means passed.
- Mapping: NIST:MEASURE-2.7, EU:Art.15, LLM01.

### AUD-903 Model changed since last report (medium, `REPORTED <age>`)

- Control (T2): re-measure after every model id change; keep `models[]` in the report in
  step with the code. An undated report yields "report age unknown" under UNKNOWN.
- Mapping: NIST:MEASURE-2.5, NIST:MANAGE-4.1, EU:Art.15, LLM03.

### AUD-904 No benign corpus (medium)

- Control (T2): add benign cases that a naive guard would flag (security questions, test
  code quoting an attack, docs with `### System:` headings) and assert they survive.
  Attacks alone make "block everything" the optimal guard.
- Mapping: NIST:MEASURE-2.5, NIST:MEASURE-2.6, EU:Art.15.

## P10 Governance

### AUD-1001 No system card (low)

- Control (T2): `aisg init --defaults` writes `ai-system-card.yaml`; fill in purpose, data,
  models, incident contact.
- Mapping: EU:Art.11, EU:Art.13, NIST:GOVERN-1.2, NIST:MAP-1.1.

### AUD-1002 Risk tier undetermined (info)

- Control (T2): the operator records their determination on the system card. Classification
  under Art. 6 / Annex III is a legal determination made by the operator, not a tool output;
  the audit does not infer a tier and you must not either.
- Mapping: EU:Art.6, EU:Art.9, NIST:MAP-1.1, NIST:GOVERN-1.2.

### AUD-1003 Annex III domain keywords without card category (info)

- Control (T2): if the prompts really do cover such a domain, record the category on the
  system card so the operator's determination is visible; if they do not, say so on the
  card. This never fires on README or CHANGELOG text.
- Mapping: EU:Art.6, EU:Art.9, NIST:MAP-1.1, NIST:GOVERN-1.2.
