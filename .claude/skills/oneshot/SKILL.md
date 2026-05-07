---
description: "OneShot: paste a prompt, the orchestrator delivers it."
argument-hint: "<your prompt, specs, project, goal, etc.>"
---

Run a OneShot for this:

$ARGUMENTS

Before starting, check whether the current workspace contains OneShot repo files:

- SYSTEM.md
- skills/orchestrator.md
- vault/

If those files exist, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in that repo as the source of truth, not chat memory.

If those files do not exist, do not ask the user to install the OneShot repo. The plugin is enough. Run in OneShot plugin mode:

1. Use the current Claude workspace as the work area.
2. Create or reuse `.oneshot/` in that workspace for durable state when file access is available.
3. Create `.oneshot/projects/<slug>.md` for the goal, assumptions, plan, checkpoints, validation, blockers, and handoff.
4. Create `.oneshot/proof/` for command results, screenshots, notes, checklists, or other evidence when useful.
5. If file access is unavailable, keep the same structure in the conversation and tell the user that durable resume files could not be written.
6. Use machine-local time for timestamps when a shell/date tool is available. Otherwise use the current chat date and say that it was not machine-verified.
7. Continue until the result is delivered, validated, or blocked by a real external constraint.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.

Do not make the user care about the internal process. In the final handoff, tell them what was delivered, where it is, what was checked, and what still needs their attention.
