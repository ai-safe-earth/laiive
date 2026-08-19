# Contributing

Thanks for helping improve **laiive**!

---

## Branches

Two branches live forever:

| branch | what it is |
| --- | --- |
| `main` | **production.** What is deployed, or about to be. Only `develop` merges into it, through a release PR. Protected: pull request required, every check green, no force-push, no deletion. |
| `develop` | **the trunk.** The default branch and where all work lands. Always deployable in principle, not necessarily deployed. |

Everything else is short-lived and named `<type>/<kebab-desc>` — `feat/voice-tuner`,
`fix/cypher-limit`, `docs/…`, `chore/…`, `refactor/…`. Branch from `develop`, open the
PR against `develop`, and let GitHub delete the branch on merge.

Two archives are never built on: `legacy/pre-refactor` (the tree as it stood before
the refactor merged, also tag `pre-refactor-main`) and `experiment/k3s`.

```
feat/…  ─┐
fix/…   ─┼─▶ develop ──(release PR)──▶ main ──▶ tag + deploy
         │      │                        │
hotfix/… ┘      └─ preview build         └─ production build
     └─────────────▶ main, then merged back into develop
```

**Merges keep every commit.** No squashing: the commit bodies here carry the reasoning
for the change, and squashing flattens a branch's worth of that into one blob. Merge
commits on both legs.

### Releasing

1. Open a PR from `develop` to `main` titled `release: vX.Y.Z`. CI must be green.
2. Merge it (a merge commit, never a squash).
3. On `main`, run `make release` — `cz bump` reads the Conventional Commits since the
   last tag, picks the next version, writes the `CHANGELOG.md` section, commits and
   tags. Push the commit and the tag.
4. Deploy: `make fly-deploy-*` per `DEPLOY.md`; Cloudflare Pages builds `main` on its own.
5. Merge `main` back into `develop` so the release commit and tag are not stranded.

### Hotfixes

Branch from `main`, PR into `main`, release as above — then merge `main` into `develop`
in the same sitting. A hotfix that never comes back is how the two branches drift.

---

## How to Contribute

We follow a simple workflow to keep contributions organized:

### 1. **Start with an Issue**
- **Before writing code**, open an issue on GitHub to discuss your idea
- For bug reports: describe the problem, steps to reproduce, and expected behavior
- For features/improvements: explain the problem you're solving and your proposed solution
- For questions: ask away!

### 2. **Wait for Feedback**
- A maintainer will review your issue and provide feedback
- This ensures your contribution aligns with the project's direction
- Avoids wasted effort on changes that won't be merged

### 3. **Fork and Branch**
- Fork the repository
- Branch from `develop`, never from `main`: `git checkout -b feat/your-feature` or
  `fix/bug-description`
- Use descriptive branch names, and open the PR against `develop`

### 4. **Make Your Changes**
- Write clean, self-documenting code
- Follow our commit message guidelines below
- Add tests if applicable
- Ensure pre-commit hooks pass

### 5. **Submit a Pull Request**
- Reference the issue number in your PR description (e.g., "Fixes #123")
- Provide a clear description of what changed and why
- Keep PRs focused on a single issue/feature

### 6. **Review Process**
- Respond to feedback promptly
- Make requested changes in new commits (don't force-push during review)
- Once approved, a maintainer will merge your PR

---

## Commit Message Guidelines

We prioritize self-documenting code and meaningful commit messages. Code should clearly express **what** it does, while commit messages explain **why**.

### Format

```
<type>: <brief summary>

<detailed explanation>
- Why was this change necessary?
- What problem does it solve?
- What alternatives were considered?
```

### Types
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code restructuring
- `perf:` Performance improvement
- `docs:` Documentation
- `test:` Tests
- `chore:` Maintenance

### Example
```
refactor: Replace nested loops with hash map in findDuplicates

The O(n²) approach was causing timeouts on large datasets.
HashMap provides O(1) lookups and reduces execution time
from 2.3s to 45ms on 10k items.

Refs: #156
```

### Code Documentation Rules

**Avoid:**
- Comments restating obvious code
- Commented-out code (use git history)
- Vague TODOs and FIXMEs without context

**Include:**
- Why non-obvious decisions were made
- Complex business logic explanations
- Known limitations or edge cases
- Public API documentation
- Complex algorithms or patterns

---

## Respect & Kindness
- Be kind and polite.
- Listen to others and assume good intent.
- Disagree with ideas, not with people.

---

That's it. Let's keep things simple, safe, and respectful while building together.

---

## Recomended reading to be a good contributor

- Hunt, A., & Thomas, D. (2019). The pragmatic programmer: Your journey to mastery (20th anniversary ed.). Addison-Wesley.
