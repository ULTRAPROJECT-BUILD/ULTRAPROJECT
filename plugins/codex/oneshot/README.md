# OneShot Codex Plugin

OneShot helps Codex take one big prompt and deliver the result: app, game, site, research pack, migration, repo cleanup, plugin, or automation.

This package is the Codex-native OneShot plugin. It exposes a bundled `oneshot` skill and the full starter prompt for Codex users. It does not rely on Claude slash-command syntax and does not create a `/oneshot` command.

## Package Contents

- `.codex-plugin/plugin.json`: Codex plugin manifest with local path metadata.
- `skills/oneshot/SKILL.md`: the OneShot workflow skill.
- `assets/`: local PNG assets used by the plugin interface metadata.
- `INSTALL.md`: local install and marketplace-discovery notes.
- `LIMITATIONS.md`: supported boundaries and manual items.
- `VALIDATION.md`: checks used to prove the package shape.

Optional app, MCP, and hook files are intentionally omitted. OneShot uses the existing workspace skills, scripts, and configured MCPs from the repository instead of bundling extra integrations inside this plugin.

## Use In Codex

Codex does not upload the Claude `.plugin` file and does not use the `/oneshot` slash command. Open Codex in the OneShot repo/folder:

```bash
codex -C /path/to/OneShot
```

Then use the full starter prompt:

```text
Oneshot this:

[Your prompt, specs, project, goal, etc.]

Before starting, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in this repo as the source of truth, not chat memory.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.
```

For a full run, include the desired outcome, audience, definition of done, constraints, and proof required before delivery. You do not need to describe the internal process; describe the result you want to come back to.

## Workflow Summary

To the user, OneShot means: one prompt, full delivery. Paste the request, let the agent work, and come back to the finished result or a clear blocker report.

Under the hood, the skill instructs Codex to:

1. Verify the workspace is the OneShot repo/folder, not an unrelated folder or old source-project checkout.
2. Read the repo-level OneShot instructions.
3. Gather local context from relevant files and any existing OneShot state.
4. Decide whether the user requested planning only, a specific ticket, or a full project loop.
5. Source or build missing skills and MCPs when needed.
6. Execute scoped work without crossing ownership boundaries.
7. Validate claims with local proof.
8. Record results in project or ticket logs.
9. Hand off changed files, validation results, and limitations.

## Marketplace Metadata

The repo-local Codex marketplace file is:

```text
.agents/plugins/marketplace.json
```

Its OneShot entry points to:

```text
./plugins/codex/oneshot
```

That path resolves from the OneShot repository root.

## Status

This is a local/repo plugin package. No official marketplace submission is claimed by this package.
