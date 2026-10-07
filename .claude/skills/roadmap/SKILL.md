---
name: roadmap
description: Refresh and show the roadmap status
disable-model-invocation: true
---
1. Read the frontmatter of every file in docs/plans/ and docs/plans/done/.
2. In docs/ROADMAP.md, rewrite only the content under `## Status`:
   for each step, in the order listed above it, a table of file | status | next.
3. Flag: files with no frontmatter, a step not in the list,
   or `active` but not changed in git for 14+ days.
4. Never change anything above `## Status`.
5. Show me the result.
