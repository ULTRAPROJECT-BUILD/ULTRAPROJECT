# Limitations

This Claude package is a local OneShot plugin package, not an official marketplace submission.

## Compatibility

- The intended user-facing Claude workflow is `/oneshot`.
- Some Claude Code plugin test contexts may show the fully qualified form `/oneshot:oneshot`; that is the same OneShot skill.
- The OneShot repository/folder is required for the full Claude plugin workflow. The plugin provides the command; the repo provides the orchestrator, vault, project records, tickets, and proof trail.
- Claude must be opened in the OneShot repo/folder. If it is opened in an old source-project checkout or unrelated project folder, the skill should stop and ask the user to reopen Claude in OneShot.
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
