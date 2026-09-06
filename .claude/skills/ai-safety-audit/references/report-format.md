# Reading an `aisg audit` report

Read this before phase 2. It condenses the finding and report schema so you can present
`audit-report.json` without guessing what a field means.

## The three buckets

Every finding sits in exactly one bucket. The bucket says where the evidence came from, not
how bad the finding is.

| bucket | meaning | how it renders |
|---|---|---|
| `measured` | an external scanner ran during THIS audit and produced the finding (gitleaks, detect-secrets, pip-audit, npm audit, osv-scanner, semgrep, mcp-scan) | `MEASURED` |
| `asserted` | this audit's own rules matched code or config, OR a report file on disk was read | `[UNMEASURED]`, plus `[REPORTED <age>d, <source>]` when it came from a file |
| `unknown` | nobody checked: a scanner was not on PATH, deep analysis is not available for a language, a report was unreadable or undated, something could not be established statically | listed under UNKNOWN with `how_to_resolve` |

Rules that hold:

- `MEASURED` means a tool ran now. A `measure-report.json` or `probe-report.json` read from
  disk is never `MEASURED`; it is `REPORTED <age>` under `asserted`, and the age comes from
  the report's `generated_at`, else the file mtime, else `git log`. If none of those is
  available the report yields an UNKNOWN item ("report age unknown") and no finding.
- `UNKNOWN` is never a pass. A run with zero findings still prints the UNKNOWN block and the
  disclaimer. Present the list verbatim with its `how_to_resolve` hints.
- Absence of a finding is not evidence of safety.

## `[UNMEASURED]`

Every rule carries `measured_precision: null`. `null` means nobody has labelled a corpus for
that rule yet; it does not mean the rule is perfect and it does not mean it is noisy. An
unmeasured rule still fires by default. When you present a finding, say `[UNMEASURED]` out
loud and never invent a confidence number. `confidence.label` is always `"UNMEASURED"` in this
version; `confidence.evidence_kind` (`code`, `config`, `absence`, `tool_output`, `report`)
and `confidence.match_kind` (`grep`, `structured`, `ast`, `external`) tell you how the match
was made. A `grep` match on a non-Python sink (AUD-401..406) is rendered "co-located,
unverified": the sink and a model call share a file and an identifier, nothing more.

## `[REPORTED <age>]`

AUD-803, AUD-902 and AUD-903 read `measure-report.json` / `probe-report.json` from the target.
Their findings carry `evidence_kind: "report"` and a `report` block:

    "report": {"file": "measure-report.json", "schema": "aisg/1",
               "generated_at": null, "age_source": "mtime", "age_days": 41}

Say how old the report is and where the age came from. A 41-day-old measurement of a guard
that has since been reconfigured measures the old configuration. `aisg measure` never emits a
precision figure, so no audit rule compares one; AUD-803 reads `threshold_failures` and
`false_positive_rate` only.

## One finding

    {
      "id": "AUD-301",
      "fingerprint": "0000111122223333",
      "title": "LETHAL TRIFECTA: private data + untrusted content + external action in one scope",
      "severity": "critical",
      "priority": 3,
      "bucket": "asserted",
      "basis": "presence",
      "confidence": {"evidence_kind": "code", "match_kind": "ast", "precision": null, "label": "UNMEASURED"},
      "scope": {"kind": "function", "unit": "u1", "name": "services/agent/app.py::handle_ticket"},
      "evidence": [{"role": "private", "file": "...", "line": 52, "snippet": "..."}, ...],
      "controls": ["ASI01", "ASI02", "ASI06", "LLM01", "LLM02", "LLM06", "EU:Art.9", "EU:Art.15", "NIST:MAP-5.1", "NIST:MANAGE-2.2"],
      "recommendation": {"tier": "T3", "summary": "...", "alternatives": ["aisg ToolPolicyGuard + PIIDetector", "NeMo Guardrails flows", "Guardrails AI validators", "LLM Guard scanners"]},
      "related_lint_rules": ["EU-AIA-012a", "ALIGN-003"],
      "known_failure_modes": ["unit-level scope over-approximates in monorepos"],
      "suppressed": false,
      "gitignored": false
    }

- `severity` is blast radius (what the gap lets an attacker do), never detector confidence.
  It is not adjusted downward because a match is a grep.
- `priority` is the threat-model group (1 = blast radius, 2 = irreversible gates, 3 = trust
  boundaries, 4 = output sinks, 5 = secrets and PII, 6 = supply chain, 7 = observability,
  8 = detection guards, 9 = evaluation loop, 10 = governance). Findings sort by
  `(priority, severity, file, line)` and AUD-301 is pinned first whenever present.
- `fingerprint` is stable across renumbered lines and renamed locals; it is what
  `--baseline` compares. Record it when the user accepts a change in phase 4.
- `controls` are evidence for a human reviewer: OWASP Agentic (ASI), OWASP LLM (LLM), EU AI
  Act articles and NIST AI RMF functions the finding is relevant to. They are printed under
  "Related controls (evidence, not a verdict)". Never state or imply compliance with any of
  them.
- `sub` names a sub-finding (`AUD-101/interpreter`, `AUD-107/inert`, `AUD-701/apm-only`);
  the display id is `AUD-101/interpreter`.
- `gitignored: true` means the evidence file is excluded by `.gitignore` but was walked
  anyway (`.env*` always is). Say so: it is a developer-machine credential, not a committed one.
- Secret and PII snippets are redacted before they enter a finding (`<redacted:sk-...last4>`,
  `<redacted:email>`); there is no flag to turn that off.

## The report envelope

Key order is fixed; `schema` is first.

    schema, kind, tool, target, generated_at, disclaimer, summary, findings, measured,
    reports, unknown, external_tools, baseline, inventory, rules

- `disclaimer` opens every format: "Not an assessment of compliance with any regulation.
  Risk classification under the EU AI Act is a legal determination made by the operator, not
  a tool output. Every rule in this report is UNMEASURED ... Absence of a finding is not
  evidence of safety." Repeat its substance when you close.
- `summary`: `findings`, `by_severity`, `by_bucket`, `reported` (findings read from disk),
  `below_threshold`, `fail_on`, `unknown_items`, `unknown_by_category`
  (`tools` / `deep` / `reports` / `runtime`), `exit_code`, `top` (first finding id),
  `suppressed`, `baseline_new` (null without `--baseline`).
- `measured`: one row per scanner that ran, with `version`, `duration_ms`, `findings` and
  `network` (whether that scanner uses the network the way it normally does).
- `reports`: every on-disk aisg report that was read, with its age and the fields the rules
  consumed (`guards` for measure, `summary` for probe).
- `external_tools`: every adapter and its status: `ran`, `not_on_path`, `not_applicable`,
  `failed`, `timeout`, `skipped_by_flag` (`--no-external`), `skipped_needs_flag`
  (promptfoo needs `--run-evals` because it may call providers). Read this list to the user
  so they know which scanners did not run.
- `baseline`: `{"file": ..., "new": n, "fixed": n, "unchanged": n}` when `--baseline` was
  given. Only `new` counts toward the exit code.
- `rules`: the catalogue that ran, each with `measured_precision: null`.

## Exit codes and the fail threshold

| exit | meaning |
|---|---|
| 0 | no finding at or above `--fail-on` (default `low`), and no UNKNOWN item in a selected category when `--fail-on-unknown` is set |
| 1 | at least one finding at or above `--fail-on`, or a `new` finding against the baseline, or an UNKNOWN item in a `--fail-on-unknown` category |
| 2 | fatal: path missing, unreadable target, walker error, report unwritable; read stderr, fix, rerun |
| 130 | interrupted |

Findings below `--fail-on` are still findings. The summary line is always

    N findings (M below --fail-on <level>, not counted in exit code); K unknown items

and JSON carries `summary.below_threshold` and `summary.fail_on`. An exit code of 0 with
`M > 0` means the user chose not to fail the build on those; it does not mean they are
resolved. Present them.

`--fail-on-unknown` without a category list fails on any UNKNOWN item, which is unusable on a
runner missing any optional scanner or on a non-Python repo (deep analysis is Python-only).
The CI recipe is `--fail-on-unknown tools,reports` after installing the scanners the team
cares about.

## Inventory (`--inventory-only`)

A separate document, also `schema: "aisg/1"` first: languages, units, LLM providers and
model ids with `pinned: true|false|null` (`null` = unknown provider, no finding), tool
definitions and how many carry an approval symbol, MCP servers with transport and pinning,
host configs found, guardrail libraries, eval tooling, on-disk reports. Summarise it in five
lines or fewer in phase 1.
