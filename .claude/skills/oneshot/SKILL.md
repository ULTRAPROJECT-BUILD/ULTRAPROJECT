---
description: "OneShot: paste a prompt, the orchestrator delivers it."
argument-hint: "<your prompt, specs, project, goal, etc.>"
---

Run a OneShot for this:

$ARGUMENTS

Before starting, verify that the current workspace is the OneShot repo/folder. The installed plugin is the command surface; the repo is the execution engine.

A valid OneShot workspace must contain:

- SYSTEM.md
- skills/orchestrator.md
- vault/

It must also identify as OneShot, not as an older source-project checkout. Check at least one of these identifiers:

- README.md contains "# OneShot"
- oneshot.py exists
- pyproject.toml identifies the project as oneshot

If the current workspace is missing those files, do not run. Tell the user: "OneShot needs both the OneShot repo/folder and the Claude plugin. Open Claude in the OneShot folder, then run `/oneshot` again."

If the current workspace appears to be an older source-project checkout instead of OneShot, do not use that vault. Tell the user to open the actual OneShot repo/folder and run `/oneshot` again.

When the workspace is verified as OneShot, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in that OneShot repo as the source of truth, not chat memory.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.

Do not make the user care about the internal process. In the final handoff, tell them what was delivered, where it is, what was checked, and what still needs their attention.
