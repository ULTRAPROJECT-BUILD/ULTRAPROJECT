# OneShot Claude Code Plugin

OneShot helps Claude take one big prompt and deliver the result: app, game, site, research pack, migration, repo cleanup, plugin, or automation.

This package is the Claude-facing OneShot plugin package. It is upload-ready as a `.zip` or `.plugin` artifact; it does not claim official marketplace submission.

End users do not need the whole OneShot repository to use the Claude plugin. The installed plugin contains the OneShot workflow instructions. If the user's workspace does not contain OneShot repo files, the skill runs in plugin mode and stores progress in `.oneshot/` when file access is available.

## Entrypoint

- Primary user-facing skill: `/oneshot <your prompt, specs, project, goal, etc.>`

Upload the package, enable OneShot, then invoke OneShot from the slash menu with `/oneshot`. The prompt lives at `skills/oneshot/SKILL.md` and uses the operator-approved strict OneShot starter contract plus plugin-only fallback mode. The package intentionally avoids legacy `commands/` files and duplicate skill/command pairs, so the installed plugin presents one clean OneShot entry.

Some Claude Code plugin test contexts display the fully qualified form `/oneshot:oneshot`. That is the same skill. The intended user-facing surface is `/oneshot`.

## What The Workflow Does

To the user, OneShot means: one prompt, full delivery. Paste the request, let the agent work, and come back to the finished result or a clear blocker report.

Under the hood, OneShot asks the agent to:

- use the installed plugin instructions, or read repo-level OneShot instructions when the workspace includes them
- preserve workspace files and OneShot state records as the source of truth
- create or update projects and tickets
- honor user scope, ticket ownership, and requested proof
- source or build missing capabilities when needed
- execute only the scoped work
- validate claims with evidence
- record checkpoints and close tickets only when acceptance criteria are met

## Starter Prompts

```text
OneShot this: build the app described below and keep going until it runs locally.
```

```text
Run OneShot for this prompt and deliver the finished result.
```

```text
OneShot this game idea. I want to paste the prompt now and come back to a playable build.
```

## Package Layout

```text
plugins/claude/oneshot/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── oneshot/
│       └── SKILL.md
├── README.md
├── INSTALL.md
├── LIMITATIONS.md
└── VALIDATION.md
```

Only `.claude-plugin/plugin.json` belongs under `.claude-plugin/`. Skills stay at the package root.

## Install And Validation

See `INSTALL.md` for Claude Code local load, local marketplace install, and Claude.ai/Cowork ZIP upload steps. See `VALIDATION.md` for static validation commands and expected proof.

Build uploadable Claude/Cowork artifacts from the repo root:

```bash
scripts/package_claude_plugin.sh
```
