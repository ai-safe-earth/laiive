#!/bin/bash
cd "$CLAUDE_PROJECT_DIR"
echo "## Open plans (step | status | file)"
for f in docs/plans/*.md; do
  [ -e "$f" ] || continue
  s=$(grep -m1 '^status:' "$f" | cut -d' ' -f2)
  st=$(grep -m1 '^step:' "$f" | cut -d' ' -f2)
  echo "${st:-?} | ${s:-?} | $f"
done | sort
