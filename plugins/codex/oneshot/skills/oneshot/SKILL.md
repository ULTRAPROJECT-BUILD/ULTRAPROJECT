---
name: oneshot
description: "OneShot: One prompt. Full delivery inside a local OneShot workspace."
---

# OneShot

Use this skill when the user asks Codex to "OneShot" a goal, build an app or game from a prompt, deliver a serious request in one run, turn a request into tracked work and proof, or execute a specific OneShot item. This is a Codex skill surface, not a Claude slash command.

To the user, OneShot means: paste the request, let the agent work, and come back to full delivery or a clear blocker report. The plan, context, tickets, and proof are supporting machinery, not the pitch.

## Starter Prompt Contract

Mirror the repository README's starter workflow. A good OneShot request includes:

- The outcome the user wants.
- The audience or operator who will use the result.
- What "done" means.
- Constraints, permissions, and things not to change.
- The proof expected before delivery.

The canonical starter form is:

```text
Run a OneShot for this:

[Your prompt, specs, project, goal, etc.]

Before starting, check whether the current workspace contains `SYSTEM.md`, `skills/orchestrator.md`, and `vault/`. If those files exist, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. If they do not exist, run in OneShot plugin mode and create `.oneshot/` state in the current workspace.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.
```

## Workflow

1. Confirm the local workspace root.
2. If the workspace contains `SYSTEM.md`, `skills/orchestrator.md`, and `vault/`, read `SYSTEM.md` and `skills/orchestrator.md`, especially the Critical Rules block. Treat those files as source of truth.
3. If those files do not exist, do not ask the user to install the OneShot repo. The plugin is enough. Run in OneShot plugin mode:
   - Use the current Codex workspace as the work area.
   - Create or reuse `.oneshot/` in that workspace for durable state.
   - Create `.oneshot/projects/<slug>.md` for the goal, assumptions, plan, checkpoints, validation, blockers, and handoff.
   - Create `.oneshot/proof/` for command results, screenshots, notes, checklists, or other evidence when useful.
   - Use machine-local time for timestamps when possible.
4. Gather only the context needed for the user's goal: existing project records, current status files, relevant docs, code, and proof artifacts.
5. Decide the mode:
   - If the user asks for planning, specification, review, or a brief only, create or update the appropriate plan/proof records and do not begin implementation.
   - If the user names a ticket, execute only that ticket and respect its file ownership, blockers, acceptance criteria, and work log.
   - If the user gives a new large goal, create or update a OneShot project plan, tickets, validation checks, and proof expectations before implementation spreads out.
6. Source or build missing capabilities when the work requires them. Prefer existing local skills, MCPs, scripts, and repo patterns before adding new machinery.
7. Execute scoped work until the acceptance criteria are met or every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint.
8. Validate claims with concrete evidence: command output, tests, screenshots, audits, reviews, manifests, or other proof appropriate to the task.
9. Record results on disk. Update project or ticket work logs with changed files, validation results, blockers, assumptions, and residual risks.
10. Deliver a concise handoff: what changed, where it lives, what passed, what was not run, and what remains manual or infrastructure-dependent.

## Boundaries

- Do not reduce scope, quality, proof requirements, public-surface polish, or delivery obligations unless the user explicitly approves that change.
- Do not reinterpret a request as a prototype, draft, MVP, plan, scaffold, partial implementation, or best effort unless the user used those words.
- When ambiguity exists, do not choose the smaller or easier interpretation; record assumptions and continue on the path that maintains or increases the requested outcome.
- Do not claim official marketplace availability, unattended external automation, credentialed integrations, spending, or external communications unless the workspace contains proof and the user has approved the required setup.
- Do not borrow Claude slash-command semantics in Codex. Use this skill and the plugin's starter prompts as the Codex entry surface.
- When another agent owns a path, avoid editing it. If ownership conflicts block the work, record the blocker and ask for direction.
