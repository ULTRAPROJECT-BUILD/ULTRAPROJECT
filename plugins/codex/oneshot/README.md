# OneShot Codex Plugin

OneShot helps Codex take one big prompt and deliver the result: app, game, site, research pack, migration, repo cleanup, plugin, or automation.

This package is the Codex-native OneShot plugin. It exposes a bundled `oneshot` skill and short starter prompts for Codex users. It does not rely on Claude slash-command syntax and does not create a `/oneshot` command.

## Package Contents

- `.codex-plugin/plugin.json`: Codex plugin manifest with local path metadata.
- `skills/oneshot/SKILL.md`: the OneShot workflow skill.
- `assets/`: local PNG assets used by the plugin interface metadata.
- `INSTALL.md`: local install and marketplace-discovery notes.
- `LIMITATIONS.md`: supported boundaries and manual items.
- `VALIDATION.md`: checks used to prove the package shape.

Optional app, MCP, and hook files are intentionally omitted. OneShot uses the existing workspace skills, scripts, and configured MCPs from the repository instead of bundling extra integrations inside this plugin.

## Use In Codex

Add the OneShot repository as a Codex plugin marketplace source:

```bash
codex plugin marketplace add /path/to/OneShot
```

Then open Codex on the project you want OneShot to work on and use one of the starter prompts:

```text
OneShot this app idea. Keep going until it runs locally.
Run OneShot for this prompt and deliver the finished result.
OneShot this game idea. I want to paste the prompt now and come back to a playable build.
```

For a full run, include the desired outcome, audience, definition of done, constraints, and proof required before delivery. You do not need to describe the internal process; describe the result you want to come back to.

## Workflow Summary

To the user, OneShot means: one prompt, full delivery. Paste the request, let the agent work, and come back to the finished result or a clear blocker report.

Under the hood, the skill instructs Codex to:

1. Use repo-level OneShot instructions when the workspace includes them, or plugin mode when it does not.
2. Gather local context from relevant files and any existing OneShot state.
3. Decide whether the user requested planning only, a specific ticket, or a full project loop.
4. Source or build missing skills and MCPs when needed.
5. Execute scoped work without crossing ownership boundaries.
6. Validate claims with local proof.
7. Record results in project or ticket logs.
8. Hand off changed files, validation results, and limitations.

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
