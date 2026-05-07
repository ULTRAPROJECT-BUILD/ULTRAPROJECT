# Limitations

This Claude package is a local OneShot plugin package, not an official marketplace submission.

## Compatibility

- The intended user-facing Claude workflow is `/oneshot`.
- Some Claude Code plugin test contexts may show the fully qualified form `/oneshot:oneshot`; that is the same OneShot skill.
- The full OneShot repository is not required for Claude plugin users. They still need to open Claude in the workspace or folder where the work should happen. If repo files are missing, the skill runs in plugin mode and creates `.oneshot/` state in the active workspace when file access is available.
- The installed package intentionally uses the current `skills/oneshot/SKILL.md` layout and does not include a legacy `commands/` file or uppercase `/ONESHOT` command, so users see one OneShot entry instead of duplicate cards.
- Codex and other hosts should use their own plugin or skill invocation surfaces rather than Claude slash-command syntax.

## Infrastructure-Dependent Checks

The following depend on the local host environment and authentication state:

- `claude --plugin-dir ./plugins/claude/oneshot`
- interactive `/reload-plugins`
- Claude marketplace catalog add/install commands

If the Claude CLI is unavailable or unauthenticated, static package validation can still pass, but live load remains infrastructure-dependent.

## Workflow Limits

OneShot can help an agent plan, execute, validate, and record proof. It does not bypass real-world constraints:

- credentials must be supplied by the operator
- paid services need explicit setup and spending controls
- legal, financial, and external communication actions need operator approval
- official marketplace submission requires a separate approved release step

## Source Of Truth

The workflow relies on repository files and vault records. If a chat message conflicts with a ticket, project file, or explicit write-ownership rule, verify and resolve the conflict before editing.
