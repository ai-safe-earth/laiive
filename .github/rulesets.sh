#!/usr/bin/env bash
#
# Branch rulesets for ai-safe-earth/laiive, as code.
#
# They are not applied by CI — a workflow that can rewrite its own required
# checks is not a gate. Run this by hand, with a token that can administer the
# repo, whenever the intended protection changes:
#
#     bash .github/rulesets.sh
#
# ORDERING: a required status check that GitHub has never seen blocks every PR
# indefinitely. Add a new context to `ci.yml` and merge it *first*, let it report
# once, and only then name it here.
#
# The two branches differ in exactly one way: `main` additionally dismisses stale
# reviews and requires review threads resolved. The CI bar is identical, because
# `develop` is meant to be always-deployable — a trunk with a lower bar than
# production is a trunk that breaks production at release time.
set -euo pipefail
REPO=ai-safe-earth/laiive

# Repository role 5 = admin. Bypass exists so `make release` and an emergency
# revert are not hostage to a green runner.
BYPASS='[{ "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }]'

# `ci-ok` is one aggregating job (see ci.yml) rather than the eleven
# matrix-generated contexts this used to name — "node (services/gateway, true)"
# and friends. Rename a matrix entry and a directly-required context silently
# stops reporting, and the PR hangs forever waiting on a job that no longer
# exists under that name.
CHECKS='{
  "strict_required_status_checks_policy": true,
  "do_not_enforce_on_create": false,
  "required_status_checks": [
    { "context": "pre-commit" },
    { "context": "commit-lint" },
    { "context": "ci-ok" }
  ]
}'

# Merge only. CONTRIBUTING.md makes the commit bodies the reasoning and `cz bump`
# reads them to write CHANGELOG.md — squashing throws both away. The repo-level
# settings already disable squash and rebase; this keeps the ruleset from
# disagreeing with them.
MERGE='["merge"]'

# --- develop: the trunk -------------------------------------------------------
# Before this it carried deletion + non_fast_forward and nothing else, so a
# red-CI pull request merged straight into the branch everything is cut from.
# Zero approvals: solo repo, the point is the checks, not a rubber stamp.
gh api -X PUT "repos/$REPO/rulesets/21041554" --input - <<JSON
{
  "name": "develop is the trunk",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/develop"], "exclude": [] } },
  "bypass_actors": $BYPASS,
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": $MERGE
      } },
    { "type": "required_status_checks", "parameters": $CHECKS }
  ]
}
JSON

# --- main: production ---------------------------------------------------------
# Only ever receives a release PR from develop.
gh api -X PUT "repos/$REPO/rulesets/21041549" --input - <<JSON
{
  "name": "main is production",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "bypass_actors": $BYPASS,
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": $MERGE
      } },
    { "type": "required_status_checks", "parameters": $CHECKS }
  ]
}
JSON

# --- retire the duplicate -----------------------------------------------------
# `main_protection` (8850576) predates `main is production` and both were active
# on refs/heads/main, each with its own pull_request rule and different
# parameters. GitHub intersects overlapping rulesets, so the effective policy was
# something neither one stated. Its two useful settings are folded in above.
if gh api "repos/$REPO/rulesets/8850576" >/dev/null 2>&1; then
  gh api -X DELETE "repos/$REPO/rulesets/8850576"
  echo "deleted duplicate ruleset main_protection (8850576)"
fi

echo "--- rulesets now ---"
gh api "repos/$REPO/rulesets" --jq '.[] | "\(.id)  \(.name)"'
