#!/bin/bash
grep -q '"stop_hook_active": *true' && exit 0
cd "$CLAUDE_PROJECT_DIR"
changed=$(git status --porcelain -uall)
code=$(echo "$changed" | grep -v ' docs/')
docs=$(echo "$changed" | grep ' docs/.*\.md')
if [ -n "$code" ] && [ -z "$docs" ]; then
  echo "Code changed but no plan updated. Update status/next in the relevant docs/plans file." >&2
  exit 2
fi
