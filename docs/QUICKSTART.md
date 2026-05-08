# OneShot Quickstart

OneShot has one official workflow now: open the OneShot folder in your coding agent and paste the full starter prompt.

There is no plugin to install, no slash command to remember, and no separate package to upload.

## 1. Get The Folder

Clone the repo:

```bash
git clone https://github.com/oneshot-repo/OneShot.git ~/Documents/OneShot
```

Or download the source zip from the [latest release](https://github.com/oneshot-repo/OneShot/releases/tag/v0.1.0) and unzip it somewhere permanent.

## 2. Open The Folder

Open or select the OneShot folder in Claude, Codex, or another coding agent that can read files, edit files, and run commands.

Do not open an old source-project folder or an unrelated target project folder. The OneShot folder contains the vault, project records, tickets, and proof trail.

## 3. Paste The Starter Prompt

Replace the bracketed line with your actual request:

```text
Run a OneShot for this:

[Your prompt, specs, project, goal, etc.]

Before starting, check whether the current workspace contains OneShot repo files:

SYSTEM.md
skills/orchestrator.md
vault/

If those files exist, and before starting the project, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in that repo as the source of truth, not chat memory. DO NOT RUN UNLESS THESE FILES ARE READ END TO END.

Follow the orchestrator/executor split exactly. The orchestrator may create the project shell, snapshot directories, checkpoint logs, and ticket metadata inline. The orchestrator must not author project plans, creative briefs, deliverables, QC reports, polish reviews, gate reports, claim ledgers, or verification manifests inline. Those require the delegated skill, spawned executor, or gate-review path described in orchestrator.md.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.
```

## Write A Better Request

You can paste a rough ask, but better prompts usually include:

- **Goal:** the concrete result you want.
- **Audience:** who will use or judge it.
- **Done means:** what must exist before the work is finished.
- **Constraints:** stack, style, budget, files, timing, and things to avoid.
- **Proof:** tests, screenshots, citations, reports, command output, or reviews.

You do not need to describe OneShot's internal process. Describe the result you want to come back to.

## Let It Run

OneShot is for work that may take an hour, a day, or a longer resumed project. It keeps the agent aimed at full delivery: files changed, checks run, assumptions recorded, blockers named, and handoff clear.

OneShot does not run as a hidden background service. The active Claude, Codex, or compatible local agent does the work while the OneShot folder supplies the delivery workflow.

## Resume Later

If the session ends, reopen the same OneShot folder in your agent and ask it to resume the active project from disk:

```text
Resume the active OneShot project in this repo. Do not create a new project.

Restore state from the latest OneShot checkpoint and continue to delivery. If more than one active OneShot project exists, ask me which one to resume.
```

Progress lives in the OneShot repo vault.

## Developer Source Setup

Use this only if you are developing OneShot or validating the repo yourself.

```bash
cd OneShot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
oneshot
```

The `oneshot` helper bootstraps local config examples and checks for an available agent CLI. The main workflow is still folder plus starter prompt.

## Next

- [README.md](../README.md) for the product overview and example prompts
- [SETUP.md](SETUP.md) for deeper environment setup
- [PUBLISHING.md](PUBLISHING.md) for public-release checks
