# Where this skill lives on each host

`aisg skill install` copies the packaged `ai-safety-audit/` folder into the directory an
agent host reads skills from. The table records what was found on each vendor page when the
package was built; `aisg skill list` prints the current flag and URL for the installed
version.

| host | project dir | global dir | verified | source |
|---|---|---|---|---|
| `claude` | `.claude/skills/` | `~/.claude/skills/` | yes | https://code.claude.com/docs/en/skills |
| `agents` | `.agents/skills/` | `~/.agents/skills/` | yes | https://agentskills.io/client-implementation/adding-skills-support |
| `codex` | `.agents/skills/` (alias of `agents`) | `~/.codex/skills/` | no | https://learn.chatgpt.com/docs/build-skills |
| `cursor` | `.cursor/skills/` | `~/.cursor/skills/` | yes | https://cursor.com/docs/context/skills |
| `gemini` | `.gemini/skills/` | `~/.gemini/skills/` | yes | https://geminicli.com/docs/cli/skills/ |
| `antigravity` | `.agents/skills/` | `~/.agents/skills/` | no | (none) |

"verified" means: as recorded at build time, the `source` page stated that directory.
`aisg skill list` shows the current flag. A host marked `no` prints a note on install
saying the location was not verified against vendor documentation; `codex` in particular
prints its resolved destination, because the vendor page (the design-time URL
`developers.openai.com/codex/skills` redirects to it) names `.agents/skills` for
repository skills and `~/.agents/skills` for user-level skills without mentioning
`~/.codex/skills`. Check the printed path against your own Codex layout.

## The `all` rule

`--host all` installs into `claude` and `agents` always, and into any other host only when
that host's directory already exists (`.cursor/` in the repo, or `~/.gemini/` with
`--global`). Installing into `.cursor/` on a machine that has never run Cursor litters the
repo. `--host all --force-all` installs everywhere regardless.

## Install commands

Project-local (the default; writes under the current repository):

    aisg skill install --host claude
    aisg skill install --host agents
    aisg skill install --host all

Global (writes under the home directory):

    aisg skill install --host claude --global

Without `aisg` on PATH, through a pinned bootstrap (`<version>` is the `AISG_VERSION`
pinned in `scripts/audit.sh`; never leave it off):

    uvx --from 'aisguard==<version>' aisg skill install --host all
    pipx run --spec 'aisguard==<version>' aisg skill install --host all

Other verbs: `aisg skill path` prints the packaged directory; `aisg skill list` prints the
host table; `aisg skill diff --host <x>` compares the installed copy with the packaged one
and exits 1 when they differ. `install` refuses to overwrite a differing copy without
`--force`; `--dry-run` prints what it would write.

## Frontmatter rule

`SKILL.md` frontmatter carries exactly two keys, `name` and `description`, and nothing else.
That is the intersection of what the hosts above accept; host-specific metadata goes in
`agents/openai.yaml`, which hosts that do not read it ignore. A test pins the key set.

## Bootstrap scripts

`scripts/audit.sh`, `audit.ps1`, `verify.sh` and `verify.ps1` resolve `aisg` in this order:
`aisg` on PATH, else `uvx --from 'aisguard==<version>'`, else
`pipx run --spec 'aisguard==<version>'`. `aisguard` is the distribution name; `aisg` is the
importable name and the console script, and on PyPI it belongs to an unrelated project, so a
bootstrap must never install by it. The version is pinned to the package
that shipped the scripts and a test asserts it equals `pyproject.toml`; an unpinned bootstrap
is what AUD-602 flags in targets, and the skill does not get an exception. When none of the
three is available, `audit.sh` exits 2 with install hints and `verify.sh` prints
`measure skipped: aisg not importable in target`.
