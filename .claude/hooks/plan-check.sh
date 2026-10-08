#!/bin/bash
grep -q '"stop_hook_active": *true' && exit 0
cd "$CLAUDE_PROJECT_DIR"
changed=$(git status --porcelain -uall)
code=$(echo "$changed" | grep -v ' docs/')
docs=$(echo "$changed" | grep ' docs/.*\.md')
# Micro changes (CLAUDE.md "Micro changes") need no plan: at most 3 files and
# 40 changed lines, untracked files counted as files.
files=$(echo "$code" | grep -c .)
lines=$(git diff HEAD --numstat -- . ':!docs' | awk '{s += $1 + $2} END {print s + 0}')
if [ "$files" -le 3 ] && [ "$lines" -le 40 ]; then
  exit 0
fi
if [ -n "$code" ] && [ -z "$docs" ]; then
  echo "Code changed but no plan updated. Update status/next in the relevant docs/plans file (micro changes are exempt: 3 files, 40 lines)." >&2
  exit 2
fi
