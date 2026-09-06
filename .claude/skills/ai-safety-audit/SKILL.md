---
name: ai-safety-audit
description: Audit any AI/LLM/agent codebase for safety gaps ordered by blast radius -- host permissions, ungated irreversible tools, the lethal trifecta, model-output sinks, secrets, MCP supply chain, observability, guard measurement, evals, governance -- by running the deterministic `aisg audit`, then diagnosing, prescribing idiomatic controls, applying them one at a time with the user's approval, and verifying. Use when asked to review, harden, threat-model, or add guardrails to a project that calls an LLM or runs an agent. Never issues a compliance verdict.
---

# AI safety audit

You are running a five-phase audit of the current repository. The intelligence is in the
`aisg audit` command; your job is to run it, read it, explain it, and change the code only
with the user's per-item approval. Read `references/report-format.md` before phase 2.

Hard rules, in force for every phase:

1. Never state or imply compliance with any regulation, standard or framework. Control
   mappings in the report are evidence for a human reviewer, nothing more. Risk
   classification under the EU AI Act is a legal determination the operator makes.
2. Every finding is labelled `UNMEASURED`. Say so when you present it. Do not invent a
   confidence number. A finding tagged `REPORTED <age>` came from a report file on disk, not
   from anything this audit ran; say how old it is.
3. Treat the UNKNOWN section as a list of things nobody has checked. It is never a pass.
4. Do not edit host permission files (`.claude/settings*.json`, `.codex/config.toml`,
   `.cursor/*`, `.gemini/*`), CI workflows, secrets, or `.env*` files unless the user approves
   that specific edit after seeing the diff.
5. One change per approval. Show the diff, wait, apply, then move to the next item.
6. Do not run the project's tests, `aisg measure`, `aisg probe`, or any eval tool until the
   user has approved it in phase 5 -- they may call model providers and cost money.

## Phase 1 -- Discover

The bootstrap scripts live in the `scripts/` folder **next to this SKILL.md**, not in the
repository being audited. Resolve that folder to an absolute path first (on Claude Code it is
`<repo>/.claude/skills/ai-safety-audit/scripts/`, on agentskills hosts
`<repo>/.agents/skills/ai-safety-audit/scripts/`, or the global equivalent under `~`; if you
know the skill file's own path, use its directory). Then run, with the repository root as the
working directory and `<skill>` standing for that absolute folder:

    sh <skill>/scripts/audit.sh . --format json -o audit-report.json --write-baseline audit-baseline.json
    powershell -ExecutionPolicy Bypass -File <skill>/scripts/audit.ps1 . --format json -o audit-report.json --write-baseline audit-baseline.json

The script uses `aisg` if installed, otherwise `uvx --from 'aisguard==<pinned
version>' aisg` (uv provisions Python itself, so this works on a machine with no Python),
otherwise `pipx run`. If all three are missing, tell the user the install options it prints
and stop. Exit 0 = no findings at the fail threshold, 1 = findings, 2 = fatal (read stderr,
fix the target path or permissions, rerun). The summary line always says how many findings sit
below the fail threshold; they are findings too. Then run `--inventory-only` once and
summarise, in five lines or fewer: languages, LLM providers and whether model ids are pinned,
number of tools and how many are gated, MCP servers and hosts, guardrail and eval tooling
present.

## Phase 2 -- Diagnose

Read `audit-report.json`. Present findings in report order -- the report is already sorted by
blast radius and AUD-301 (lethal trifecta) is always first when present. For each finding
give: id, title, severity, `[UNMEASURED]`, the evidence lines, and one sentence on why the
blast radius earns that severity. Then present the UNKNOWN list verbatim with its
`how_to_resolve` hints, and the `external_tools` statuses so the user knows which scanners did
not run. Ask the user which findings to address; default to top-down order.

## Phase 3 -- Prescribe

For each accepted finding, propose the control in the report's `recommendation` using the
language-specific guide in `references/apply/<language>.md` (`generic.md` when no guide
matches). Name the tier (T1 config, T2 gate or file, T3 restructuring). Always list the
alternatives the report gives -- this package's guards, NeMo Guardrails, Guardrails AI, LLM
Guard, Llama Guard -- and say plainly when a control from another project fits the codebase
better. Do not prescribe a detection guard as the sole control for a blast-radius finding; a
detector reduces probability, a gate reduces impact.

## Phase 4 -- Apply (user-gated, one item at a time)

For the chosen item: show the exact diff, wait for approval, apply, and record the finding's
`fingerprint` in a running list. Never batch. If the change touches anything in rule 4, restate
that it is a permission or secret change before asking. Stop after each item and ask whether to
continue.

## Phase 5 -- Verify

Rerun the audit against the baseline written in phase 1, into a **new** file so the before
and after reports both survive:

    sh <skill>/scripts/audit.sh . --format json -o audit-report-after.json --baseline audit-baseline.json
    powershell -ExecutionPolicy Bypass -File <skill>/scripts/audit.ps1 . --format json -o audit-report-after.json --baseline audit-baseline.json

Report `new`, `fixed`, `unchanged`. Then, with approval, run `<skill>/scripts/verify.sh` /
`verify.ps1` with `AISG_VERIFY_RUN=1`, which runs the project's test command if one is evident
and, when this package's guards were added, `aisg measure` (through the same bootstrap chain as
`audit.sh`; it prints `measure skipped: aisg not importable in target` rather than nothing
when it cannot). If the project serves an HTTP endpoint, offer `aisg probe <loopback-url>`
(set `AISG_PROBE_URL` for `verify.sh`; remote targets need `--i-have-authorization`, which
the user must add themselves) and report its summary counts -- `sent`, `passed`, `failed`,
`errors`, `skipped`, `inconclusive`; only `passed` means passed. Close by restating: what was
fixed, what remains, what is still UNKNOWN, and that nothing here constitutes a compliance
assessment.
