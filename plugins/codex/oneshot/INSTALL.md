# Install OneShot For Codex

## Local Repository Use

The plugin package lives at:

```text
plugins/codex/oneshot
```

The repo-local marketplace metadata lives at:

```text
.agents/plugins/marketplace.json
```

## Use From Codex

Codex does not upload the Claude `.plugin` file. Open Codex in the OneShot repo/folder:

```bash
codex -C /path/to/OneShot
```

Then start with the full starter prompt:

```text
Run a OneShot for this:

[Your prompt, specs, project, goal, etc.]
Before starting, check whether the current workspace contains OneShot repo files:

SYSTEM.md
skills/orchestrator.md
vault/

If those files exist, and before starting the project, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in that repo as the source of truth, not chat memory. DO NOT RUN UNLESS THESE FILES ARE READ END TO END.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.
```

The OneShot repo/folder is required because it stores `SYSTEM.md`, `skills/orchestrator.md`, the vault, projects, tickets, and proof.

## Optional Marketplace Discovery

Some Codex setups support marketplace-source discovery. If you want this package listed as a local plugin source, add the OneShot repository:

```bash
codex plugin marketplace add /path/to/OneShot
```

This command may depend on the installed Codex version, local configuration, and authentication state. Static package validation does not require running a mutating marketplace install command.
