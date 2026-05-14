<div align="center">

# OneShot

### One prompt. Full delivery.

OneShot is a chat-native project delivery system for jobs too big for one chat. You open the OneShot folder, paste one prompt, and a coding agent keeps working until the job is finished.

Works with Claude, Codex, or any capable coding agent that can open a folder, edit files, and run commands.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-v2.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/hero-light.png">
  <img alt="OneShot" src="docs/assets/hero-v2.png">
</picture>

</div>

---

## What it does

A normal chat answers one question. OneShot keeps the agent going through the whole job — making the files, running the checks, fixing what broke, verifying the result. It can run for an hour, a day, a week, or across resumed sessions.

It pauses and asks you when it needs a password, system access, a payment, or a real human decision. Otherwise it keeps working.

The OneShot folder is the engine. It contains the instructions, vault, project records, tickets, and proof trail. There is no plugin to install and no slash command to remember.

## Install

You need the **OneShot folder** and a coding agent.

Clone the repo:

```bash
git clone https://github.com/oneshot-repo/OneShot.git ~/Documents/OneShot
```

Or download the source zip from the [latest release](https://github.com/oneshot-repo/OneShot/releases/tag/v0.2.0) and unzip it somewhere you can keep it.

Then open or select the OneShot folder in Claude, Codex, or your coding agent. Paste this full starter prompt:

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

**Platform note:** OneShot is optimized for macOS today. On Windows, install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install), open Ubuntu, and run the steps above from inside WSL. Claude Desktop can open WSL folders via `\\wsl$\` paths. OneShot's engine is cross-platform, but a few skills assume Unix tools, so WSL is the smoother route. If you want a native Windows workflow, ask your coding agent to help adapt the setup for Windows paths and shell commands.

## How to use it

Open the OneShot folder, paste the starter prompt above, and replace the bracketed line with what you want.

**Important:** In a normal OneShot run, the orchestrator coordinates the project and spawns executor agents to do the work. If the orchestrator starts doing implementation work itself, stop the run and restart with the full starter prompt above.

For real results, tell the agent five things:

- **Goal** — what you actually want
- **Audience** — who's going to use, judge, or pay for it
- **Done means** — the specific finish line
- **Avoid** — anything off-limits, lazy, or against your taste
- **Proof** — what you want to see before it hands the work back

## What to expect

- **Big asks take real time.** Hours, sometimes longer.
- **It can use a lot of tokens.** OneShot keeps context, reviews its work, runs checks, and revises until the job is actually done; serious jobs can consume substantially more tokens than a normal chat.
- **It can't bypass logins or payments.** It pauses and asks.
- **If a session ends**, reopen your agent in the OneShot folder and tell it to resume the active OneShot.
- **It needs the OneShot folder.** The folder stores the workflow, project state, tickets, and proof.

## Safety

OneShot is powerful local automation. Through your active coding agent, it can read files, edit them, run shell commands, use connected tools, and keep working through long autonomous sessions.

Use it in an environment you control. Keep secrets and credentials out of prompts, scope connected API keys to least privilege, and use a dedicated user account or VM for risky or untrusted work.

## More

- [Architecture](docs/ARCHITECTURE.md) — how OneShot works under the hood

## License

[Apache 2.0](LICENSE). Source attribution is kept in [`NOTICE`](NOTICE).
