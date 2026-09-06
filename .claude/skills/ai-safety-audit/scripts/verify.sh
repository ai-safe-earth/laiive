#!/bin/sh
# aisg-audit: ignore-file
# ai-safety-audit verify step (phase 5). Detects the project's test command and prints it,
# then resolves `aisg` through the same pinned bootstrap chain as audit.sh for
# `aisg measure` and, when AISG_PROBE_URL is set, `aisg probe`.
# Nothing runs unless AISG_VERIFY_RUN=1: tests, measure and probe may call model providers.
# This script never adds --i-have-authorization; a remote probe target needs the user to add it.
set -u
AISG_VERSION="0.1.0"   # pinned; test_skill_package.py asserts this equals pyproject.toml [project].version
run="${AISG_VERIFY_RUN:-0}"
status=0

# --- 1. Test command, from manifests (first match wins) ---------------------
test_cmd=""
if [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -f setup.cfg ]; then
  test_cmd="pytest"
elif [ -f package.json ] && grep -q '"test"[[:space:]]*:' package.json; then
  test_cmd="npm test"
elif [ -f go.mod ]; then
  test_cmd="go test ./..."
elif [ -f Cargo.toml ]; then
  test_cmd="cargo test"
fi

if [ -z "$test_cmd" ]; then
  echo "tests: no test command detected (looked for pyproject.toml/pytest.ini/setup.cfg, package.json test script, go.mod, Cargo.toml)"
else
  echo "tests: $test_cmd"
  if [ "$run" = "1" ]; then
    # shellcheck disable=SC2086  # intentional word splitting of the detected command
    if ! $test_cmd; then
      echo "tests: FAILED ($test_cmd exited non-zero)" >&2
      status=1
    fi
  else
    echo "tests: not run (set AISG_VERIFY_RUN=1 to run)"
  fi
fi

# --- 2. aisg through the same bootstrap chain as audit.sh -------------------
have_aisg() {
  command -v aisg >/dev/null 2>&1 || command -v uvx >/dev/null 2>&1 || command -v pipx >/dev/null 2>&1
}

run_aisg() {
  if command -v aisg >/dev/null 2>&1; then
    aisg "$@"
  elif command -v uvx >/dev/null 2>&1; then
    uvx --from "aisguard==$AISG_VERSION" aisg "$@"
  elif command -v pipx >/dev/null 2>&1; then
    pipx run --spec "aisguard==$AISG_VERSION" aisg "$@"
  else
    return 127
  fi
}

# Summary counts from a probe report: sent/passed/failed/errors/skipped/inconclusive.
# `summary` is the first object carrying these keys, so the first match is the right one.
# Only `passed` means passed; the other five are never folded into it.
print_probe_summary() {
  for key in sent passed failed errors skipped inconclusive; do
    value=$(grep -oE "\"$key\"[[:space:]]*:[[:space:]]*[0-9]+" "$1" | head -n 1 | grep -oE '[0-9]+$')
    echo "probe $key: ${value:-?}"
  done
  echo "probe: only 'passed' means passed; failed, errors, skipped and inconclusive are separate"
}

if ! have_aisg; then
  echo "measure skipped: aisg not importable in target" >&2
  if [ -n "${AISG_PROBE_URL:-}" ]; then
    echo "probe skipped: aisg not importable in target" >&2
  fi
  exit "$status"
fi

# --- 3. aisg measure, when a pipeline config exists -------------------------
pipeline_cfg=""
for candidate in guardrails.yaml aisg.yaml config/*.yaml config/*.yml; do
  [ -f "$candidate" ] || continue
  if grep -Eq '^(pipeline|guards):' "$candidate"; then
    pipeline_cfg="$candidate"
    break
  fi
done

if [ -z "$pipeline_cfg" ]; then
  echo "measure: no pipeline config found (looked for guardrails.yaml, aisg.yaml, config/*.yaml with a top-level pipeline: or guards: key)"
else
  echo "measure: aisg measure --config $pipeline_cfg -o measure-report.json"
  if [ "$run" = "1" ]; then
    if ! run_aisg measure --config "$pipeline_cfg" -o measure-report.json; then
      echo "measure: FAILED (aisg measure exited non-zero)" >&2
      status=1
    fi
  else
    echo "measure: not run (set AISG_VERIFY_RUN=1 to run)"
  fi
fi

# --- 4. aisg probe, only when AISG_PROBE_URL is set --------------------------
if [ -n "${AISG_PROBE_URL:-}" ]; then
  echo "probe: aisg probe $AISG_PROBE_URL -o probe-report.json"
  echo "probe: a non-loopback target needs --i-have-authorization; this script never adds it"
  if [ "$run" = "1" ]; then
    if ! run_aisg probe "$AISG_PROBE_URL" -o probe-report.json; then
      echo "probe: exited non-zero (1 = a case got through, 2 = errors/skipped/inconclusive present)" >&2
      status=1
    fi
    if [ -f probe-report.json ]; then
      print_probe_summary probe-report.json
    fi
  else
    echo "probe: not run (set AISG_VERIFY_RUN=1 to run)"
  fi
fi

exit "$status"
