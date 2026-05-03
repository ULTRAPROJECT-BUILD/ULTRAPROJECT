# Quickstart

The 5-minute path from `git clone` to a running ultraprompt.

## 1. Prerequisites

- macOS or Linux, Python 3.9+, Node 18+
- An authenticated AI coding tool such as [Claude Code](https://claude.com/claude-code), [Codex CLI](https://github.com/openai/codex), [OpenCode](https://opencode.ai/), a VS Code-style editor agent, a desktop app, or another GUI agent that can open this folder, read and edit files, run shell commands, and follow long repo instructions. A plain web chat without repo and terminal access is not enough.
- Optional: `ripgrep`, `gh`

If you need a deeper environment setup, see [SETUP.md](SETUP.md).

## 2. Clone And Install

```bash
git clone https://github.com/ULTRAPROMPT-BUILD/ULTRAPROMPT
cd ULTRAPROMPT
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

This installs the `ultraprompt` command on your PATH (the editable install means the repo source is what runs). The `pip` upgrade is required because pre-22.0 versions don't support editable installs from a `pyproject.toml` without a `setup.py`.

## 3. Bootstrap

```bash
ultraprompt
```

Copies `.env.example` → `.env`, `.mcp.example.json` → `.mcp.json`, and `vault/clients/_registry.example.md` → `vault/clients/_registry.md` if any are missing, then verifies that `claude`, `codex`, or `opencode` is on your PATH.

Edit `.env` and `.mcp.json` with your own credentials. Leave the templates alone — they're the source of truth for new installs. Never commit either of the live files.

## 4. Run An Ultraprompt (Chat-Native)

Project execution is chat-native — there is no `ultraprompt run` command. Open your AI coding tool pointed at this repo and paste:

> *"Read SYSTEM.md and skills/orchestrator.md — **especially the Critical Rules block at the top of orchestrator.md, those are load-bearing**. Follow the skill literally. Here's what I want to build: \<your prompt, specs, or rough description\>. Be strict about acceptance criteria, run to completion — don't stop, pause, or ask clarifying questions unless I (the operator) explicitly tell you otherwise."*

Auth is whatever your tool is configured for — Claude Code's subscription, Codex's, OpenCode's configured provider, or your own API keys.

The orchestrator will:

1. Decide whether the goal is a known pattern or a frontier project.
2. Generate a project plan with phases, waves, tickets, and gates.
3. Spawn executor agents one ticket at a time and route by task type.
4. Require evidence (commands, screenshots, walkthrough videos, audit logs) before any ticket closes.
5. Run quality, polish, and credibility gates before delivery.
6. Record everything in `vault/` so the next session can resume from files.

## 5. Watch It Work

Open the project's `status.md` in any markdown viewer (Obsidian, VS Code preview, GitHub):

```
vault/projects/<your-project>.derived/status.md
vault/clients/<client>/projects/<your-project>.derived/status.md   # client-scoped
```

It's regenerated whenever the orchestrator refreshes context — phase, current wave, active tickets, blocked tickets, recently closed, and the latest checkpoint, all on one screen.

You can also tail the project file directly. Every orchestrator decision lands in `vault/projects/<your-project>.md` under `## Orchestrator Log` as an `ORCH-CHECKPOINT` line — that's how the next session resumes cold.

## 6. If A Session Ends Mid-Flight

Token exhaustion, model switch, machine restart, or operator interruption — none of it loses progress. Just point a fresh AI coding tool session at the repo with the same prompt, and it picks up from the last `ORCH-CHECKPOINT`.

The default `agent_mode` is `chat_native` — everything routes to whichever tool is hosting the chat. Claude Code and Codex have the most tested deeper routing support today. If you're running cross-model (`agent_mode: normal`) and one CLI is exhausted, flip to a single-agent override:

```bash
python3 scripts/set_agent_mode.py chat_native       # default — auto-route to host CLI
python3 scripts/set_agent_mode.py claude_fallback   # explicit override → all work to Claude
python3 scripts/set_agent_mode.py codex_fallback    # explicit override → all work to Codex
python3 scripts/set_agent_mode.py normal            # cross-model routing (requires both CLIs)
```

## 7. Where To Go Next

- [ARCHITECTURE.md](ARCHITECTURE.md) — the mental model: vault, tickets, gates, routing, recovery
- [SETUP.md](SETUP.md) — deeper environment setup, optional integrations, Playwright/browser setup
- `SYSTEM.md` — the system prompt every agent reads
- `vault/SCHEMA.md` — the markdown/frontmatter schema for project memory
- `skills/orchestrator.md` — the core loop in detail
- `vault/config/platform.md` — agent routing, quality contract, fallback modes

## Tips

- **Don't overthink the first goal.** A small project — landing page, research brief, data analysis — exercises the whole loop end-to-end and teaches you the rhythm.
- **Read the project plan before the first executor spawns.** The orchestrator writes the plan to `vault/snapshots/` and waits for tickets. If the plan looks wrong, kill it and re-prompt with a tighter goal.
- **Evidence is the contract.** If a ticket claims work is done but the evidence path doesn't resolve on disk, the gates fail closed. That's the feature.
- **Read `status.md` per project.** The derived status view in `<slug>.derived/status.md` is the at-a-glance projection of the vault — phase, active tickets, blockers, recent closures. No server required.
