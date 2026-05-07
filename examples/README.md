# Examples

Starter goals you can hand to a OneShot orchestrator on day one.

Each file shows:

- the kind of work it exercises
- a copy-paste prompt
- expected scope (rough phase count + duration)
- where outputs land
- variations to adjust the difficulty or domain

## Pick one

| Example | Domain | Duration (rough) | Demonstrates |
|---|---|---|---|
| [Build a landing page](build-landing-page.md) | software / web | ~30–90 min | creative-brief → build → QC → polish review → delivery; visual evidence; design contract |
| [Research and report](research-and-report.md) | research / synthesis | ~30–60 min | creative-brief → research → write → review; cited evidence; mission alignment audit |
| [Audit a repo](audit-a-repo.md) | analysis / recommendations | ~30–60 min | external-code safety rules; read-only analysis; structured findings report |

## How to run any of them

From the repo root, with your `.env` and `.mcp.json` configured (see [docs/QUICKSTART.md](../docs/QUICKSTART.md)):

```bash
claude -p "$(cat examples/build-landing-page.md | grep -A 50 '## Prompt' | tail -n +3)"
```

or, more simply, copy the `## Prompt` block out of the example file and paste it after `claude -p` (or `codex exec`).

## What to expect

The orchestrator will:

1. Read `SYSTEM.md` and `skills/orchestrator.md`.
2. Match the goal against the [project-plan](../skills/project-plan.md) skill — produce a phased plan in `vault/snapshots/<project>/`.
3. Spawn executors for each ticket in `vault/tickets/`.
4. Require evidence (commands, screenshots, walkthroughs, audit logs) before any ticket closes.
5. Run quality, polish, and credibility gates before declaring delivery.
6. Land everything in `vault/projects/<your-project>.md` so a future session can resume cold.

If you want to watch it work, open `vault/projects/<your-project>.derived/status.md` (or the client-scoped equivalent) in any markdown viewer — Obsidian, VS Code preview, or GitHub. It refreshes whenever the orchestrator runs.

## Tips for your first run

- **Pick a small first goal.** A landing page or a one-page report exercises the entire loop end-to-end without consuming hours.
- **Don't over-specify.** The brief generator is part of the system. Give it a goal and a vibe; let the brief skill turn it into a contract.
- **Read the project plan before tickets fire.** The orchestrator writes the plan first and waits. If the plan looks wrong, kill it and re-prompt with a tighter goal.
- **Evidence is the contract.** Closed tickets must point to real artifacts on disk. Gates fail closed when claims don't match reality. That's the feature.
