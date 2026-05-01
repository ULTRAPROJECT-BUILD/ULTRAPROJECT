<div align="center">

# ULTRAPROJECT

### Start an autonomous AI project from one folder and one prompt.

ULTRAPROJECT is a ready-to-run workspace for **Claude Code** or **Codex**. Download this repo, open the folder in your AI coding tool, paste one "run an ultraproject" prompt, and the agent uses the files here to plan, build, review, verify, and resume work until the project is done. Normal use is chat-native: the included `ultraproject` command prepares local config and checks readiness; it does not run the project for you.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-early--release-yellow)](#project-status)

![ULTRAPROJECT](docs/assets/hero.png)

<br>

**For anyone who wants to build serious things without babysitting every step.**

[Start Here](#start-here-run-your-first-ultraproject) · [Prompt Template](#the-prompt-to-paste) · [Watch Progress](#watch-progress) · [Resume](#if-the-session-stops) · [Why](#why-ultraproject) · [How It Works](#how-it-works) · [Quickstart](docs/QUICKSTART.md) · [Architecture](docs/ARCHITECTURE.md) · [Setup](docs/SETUP.md)

</div>

---

## Start Here: Run Your First Ultraproject

If you are new to AI agents, use this section and ignore the architecture details until later. The whole path is: install one tool, download the repo, run the readiness setup, open the `ULTRAPROJECT` folder, paste the starter prompt, and let the agent work. You do **not** need to understand MCPs, vaults, tickets, routing, or gates before starting.

### 1. Install one AI coding tool

Install and sign in to either:

- [Claude Code](https://claude.com/claude-code)
- [Codex CLI](https://github.com/openai/codex)

One authenticated tool is enough for a first run. If you have both, ULTRAPROJECT can route work between them, but that is optional.

### 2. Download this repo

With Git:

```bash
git clone https://github.com/ULTRAPROJECT-BUILD/ULTRAPROJECT
cd ULTRAPROJECT
```

Without Git: click **Code -> Download ZIP** on GitHub, unzip it, and open the unzipped `ULTRAPROJECT` folder. If the ZIP creates a folder named something like `ULTRAPROJECT-main`, that is the folder to open.

### 3. Recommended one-time readiness setup

This installs the small `ultraproject` helper and creates local config files from the examples. This is a setup check, not a project runner.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
ultraproject
```

What this does:

- copies `.env.example` to `.env`
- copies `.mcp.example.json` to `.mcp.json`
- copies `vault/clients/_registry.example.md` to `vault/clients/_registry.md`
- checks that `claude` or `codex` is available on your PATH

For serious runs, use macOS or Linux, Python 3.9+, and an authenticated Claude Code or Codex install. Node 18+ is recommended for web apps, browser tests, and UI projects. Windows is not first-class yet because some shell hooks and runtime paths are macOS/Linux oriented.

### 4. Open this folder in Claude Code or Codex

Open the folder that contains `README.md`, `SYSTEM.md`, and `skills/orchestrator.md`. From inside that `ULTRAPROJECT` folder, start your tool:

```bash
claude
```

or:

```bash
codex
```

If you are using a graphical app, choose the `ULTRAPROJECT` folder as the workspace/project folder. Do not choose the parent folder that merely contains `ULTRAPROJECT`.

### 5. Paste the starter prompt

Use the template below. Replace the bracketed text with what you want built, researched, designed, analyzed, or delivered.

## The Prompt To Paste

```text
Run an ultraproject with this goal:

[Describe what you want built, researched, designed, analyzed, or delivered.]

Before starting, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in this repo as the source of truth, not chat memory.

Turn my goal into a project contract, phase plan, tickets, acceptance criteria, assumptions, and evidence gates. Then execute the tickets, verify work with real evidence from files/commands/screenshots/reports as appropriate, and write checkpoints so the project can resume from disk.

If details are missing, make reasonable assumptions, write them down, and keep going. Work until the project is delivered. Do not stop, pause, or ask me to continue unless I explicitly tell you to pause or every executable path is blocked.
```

That is the whole basic workflow: **download repo → open folder in Claude/Codex → paste prompt → let it run.**

### A Better First Prompt

Your ultraproject will work better if you include:

- **Goal:** what you want at the end
- **Audience:** who will judge the result
- **Done means:** specific acceptance criteria
- **Constraints:** tech stack, style, budget, deadline, files to use, things to avoid
- **Proof:** tests, screenshots, demos, citations, reports, or review standards you expect

Example:

```text
Run an ultraproject with this goal:

Build a polished local-first personal finance dashboard for a non-technical user. It should import CSV bank transactions, categorize spending, show monthly trends, and export a clean PDF summary.

Audience: someone who wants a simple private budgeting tool, not an accounting system.

Done means: a working app, clear setup instructions, sample data, screenshots, and a verification report showing the import flow, charts, and PDF export all work.

Constraints: use a boring maintainable stack, avoid paid APIs, keep the UI calm and easy to understand.

Before starting, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the repo files as the source of truth. Turn this into a project contract, phase plan, tickets, acceptance criteria, assumptions, and evidence gates. Execute the tickets, verify work with real evidence from files/commands/screenshots/reports as appropriate, and write checkpoints so the project can resume from disk. Make reasonable assumptions, write them down, and keep going. Work until the project is delivered. Do not stop, pause, or ask me to continue unless I explicitly tell you to pause or every executable path is blocked.
```

### What Happens Next

ULTRAPROJECT tells the agent how to run the work like a durable project instead of a one-off chat:

- It creates a project record in `vault/projects/` as the run's notebook.
- It breaks your request into phases and tickets, which are small work orders.
- It may hand tickets to focused executor sessions instead of doing everything in one long chat.
- It requires proof checks before work closes: real files, real commands, screenshots, reports, or other evidence.
- It writes checkpoints to disk so a future session can resume.

Project execution happens in Claude Code or Codex chat. There is no hidden daemon and no `ultraproject run` command for normal use.

### Watch Progress

The agent will create a project slug from your goal. If you do not know the slug, ask: "What project slug are you using?"

To watch progress, open:

```text
vault/projects/<project-name>.derived/status.md
```

or the canonical project log:

```text
vault/projects/<project-name>.md
```

The `status.md` file is the quick view. The project `.md` file is the durable log with decisions, checkpoints, blockers, and ticket history.

### If The Session Stops

Token limits, rate limits, restarts, and model switches are normal. Start Claude Code or Codex again in the same `ULTRAPROJECT` folder and paste:

```text
Resume the active ultraproject in this repo. Do not create a new project.

Read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Inspect vault/projects/*.md and the matching vault/projects/*.derived/status.md files, identify the active project, find the latest ORCH-CHECKPOINT, restore the current state from disk, and continue the project to delivery. Do not restart from scratch unless the project file says to. If more than one active project exists, ask me which one to resume.
```

### Common First-Run Mistakes

- Opening the parent folder instead of the `ULTRAPROJECT` folder.
- Trying to run `ultraproject run`. The `ultraproject` command only bootstraps config and readiness.
- Giving a vague goal but no "done means" criteria.
- Forgetting to say "run to completion," which makes agents pause at natural stopping points.
- Expecting a cheap quick answer. ULTRAPROJECT optimizes for quality and verification, which can use many model calls.

> **For technical reviewers:** the README is the front door. The actual operating logic lives in [skills/orchestrator.md](skills/orchestrator.md), plus [SYSTEM.md](SYSTEM.md), [skills/creative-brief.md](skills/creative-brief.md), and [skills/deliverable-standards.md](skills/deliverable-standards.md). Read `orchestrator.md` before judging the system design.

---

<div align="center">

![ULTRAPROJECT ran for 78 hours and 43 minutes on a single prompt](docs/assets/78-hours.png)

</div>

---

## Why ULTRAPROJECT

- **Tell it what you want, then walk away.** You come back to finished work, not clarifying questions.
- **One prompt, days of autonomous work.** Runs survive compaction, token exhaustion, machine restart, model swap, and operator pause — state lives on disk, not in chat memory.
- **No more "I built it!" when nothing was built.** Thirteen named, fail-closed gates verify the work against real files, real test runs, and real screenshots before anything closes. Self-certification doesn't satisfy any of them.
- **Self-extending.** When the system needs a tool it doesn't have — an MCP server, a skill, a CLI wrapper — it builds, tests, and archives one. The next project starts with that capability already on the shelf.
- **For real projects.** Most agent frameworks fall over past a few thousand lines. This is built so weeks-long, ship-quality work actually finishes.

---

## What This Is

ULTRAPROJECT is a **chat-native agent platform**. You operate it from inside Claude Code or Codex — there's a one-time bootstrap CLI (`ultraproject`) that copies example configs into place, but project execution itself is just pasting a prompt into the chat. The vault — a structured directory of markdown files with YAML frontmatter — is the source of truth. Chat history is useful but never trusted as the system of record.

You give it one prompt. The system:

1. Generates a project contract with mission alignment, proof strategy, scale matching, and acceptance criteria.
2. Decomposes the contract into phases, waves, and tickets.
3. Routes each ticket to the right model (Claude or Codex) based on `task_type`.
4. Spawns executor agents one at a time through a routing runtime that handles metering, detachment, and ticket lifecycle.
5. Runs evidence gates against actual files on disk between every meaningful state change.
6. Records every decision, blocker, artifact, and recovery checkpoint as a markdown file.
7. Resumes from exactly where it stopped if anything interrupts the run.

It works for software, design, research, content, presentations, audits, data work, or any structured project bigger than a single agent run.

## Who This Is For

**Use ULTRAPROJECT when:**

- The thing you want to build is bigger than a single chat session — multi-day, multi-thousand-LOC, multi-deliverable.
- You care more about output quality than speed or cost.
- You're willing to write a strict prompt with named acceptance criteria and an "execute to completion" directive.
- You have (or will pay for) a Claude Max plan and/or ChatGPT Pro plan.

**Don't use ULTRAPROJECT when:**

- You want a 30-second answer or a real-time chat replacement.
- The task is tightly bounded and a single chat session would do it.
- You don't want to burn tokens — the gate stack runs many model calls per ticket.
- You need a sandboxed product where the agent's actions don't touch your filesystem. Agents here run shell commands, read and write files, and (when configured) call external APIs.

## How It Works

The beginner workflow is above: download the repo, open the folder in Claude Code or Codex, paste the starter prompt. This section explains what ULTRAPROJECT asks the agent to do after that.

### The plain-English loop

1. The agent reads `SYSTEM.md` and `skills/orchestrator.md`.
2. It turns your request into a project contract: mission, assumptions, acceptance criteria, proof strategy.
3. It creates a phase plan and just-in-time ticket files in the vault.
4. It spawns executor agents for tickets instead of doing all work in one chat context.
5. It requires evidence before closing work: files, command output, screenshots, walkthroughs, reports, or reviews.
6. It writes checkpoints to disk after major steps.
7. If the session ends, a future Claude or Codex session resumes from the latest checkpoint.

Project execution is chat-native: there is no `ultraproject run` command. The `ultraproject` CLI is only a bootstrap helper that creates local config files and checks readiness. Auth is whatever your Claude Code or Codex install already uses: subscription auth, CLI auth, or your own API keys if configured.

### Two execution models

The orchestrator picks one based on the project plan's frontmatter:

- **Classic phases** — linear `Phase 1 → Phase 2 → ...` with hard exit criteria per phase. Used for most projects.
- **Capability-waves** (`execution_model: capability-waves`) — anchor phases for macro sequencing, plus a live **Capability Register** (what proof is still missing) and a **Dynamic Wave Log** (the active attack surface). Waves can close without advancing the phase. Used for frontier work where the proof program changes as the build reveals new risk.

> **Be strict with exit criteria *and* tell it not to stop.** The two things to nail in the prompt:
>
> 1. Strict acceptance criteria (named bar, specific verifications, named evaluator). The more specific you are about what "done" looks like, the harder the gate stack works to actually hit those criteria.
> 2. An explicit "do not stop, do not pause, do not ask under any circumstances" directive. Without it, agents default to asking before spending serious compute or making structural decisions — which breaks the walk-away promise.

### Watching progress (or not)

Every project gets two markdown files automatically:

- `vault/projects/<slug>.md` — canonical project log: goal, decisions, orchestrator checkpoints, full history.
- `vault/projects/<slug>.derived/status.md` — auto-regenerated at-a-glance view: phase, current wave, active tickets, blockers, recently closed.

Open either in Obsidian, VS Code preview, or GitHub. The derived view refreshes every time the orchestrator runs. Or just walk away and check back when it's done.

### Redirecting mid-flight

Edit `vault/projects/<slug>.md` directly — change the goal, drop phases, add constraints. The next orchestrator pass reads the file as truth and adjusts. For structured changes, drop a `## Pivot Requested` section in the project file and the next iteration will create the replacement project automatically.

---

## The Gate Stack

This is what makes "no hallucinated completions" real. Every gate is a `scripts/check_*.py` Python file. They are fail-closed, mechanical, and run in a defined order — not aspirational quality theater.

| Gate | What it verifies | Script |
|------|------------------|--------|
| **Quality Contract** | The brief defines a real Goal Contract, Assumption Register, and Proof Strategy — not vague intent. | `check_quality_contract.py` |
| **Brief gate** | Brief passes a 12-criterion review by an independent reviewer (`gate_reviewer` role — different model in `normal` mode, fresh-context subagent on the host in `chat_native`) against the original request. Re-closes don't count without a dated re-grade snapshot that postdates the revision. | `check_brief_gate.py` |
| **Gate packet preflight** | Mechanical check that all phase tickets are actually closed, evidence files exist on disk, and cited proof paths resolve. Catches phantom citations before the gate review runs. | `check_gate_packet.py` |
| **Build-Prove-Fix loop** | Verification manifest (build verification, test execution, functional proof, regression anchor) must hit 100% executable P0+P1 pass rate before phase advancement. | `test-manifest` skill |
| **Phase gate** | Mid-run code review by the `gate_reviewer` role — A grade required for client work and frontier capability phases. Includes mission-alignment audit and scale matching. | inline gate review |
| **Ticket evidence truth check** | A ticket's own handoff artifact can veto an over-optimistic close-out. Cited proof must resolve on disk. | `check_ticket_evidence.py` |
| **Drift detection** | Re-verifies that referenced artifacts still exist and still pass. Catches stale or fabricated references. | `detect_project_drift.py` |
| **Wave handoff / brief coverage** | Capability-waves: next wave can't activate without proven coverage and a governing brief. | `check_wave_handoff.py`, `check_wave_brief_coverage.py` |
| **Mission Completion Gate** | Verifies every non-negotiable goal from the *original* request has evidence at the scale claimed. Catches scope drift between mission and plan. Descopes require explicit admin approval. | inline orchestrator gate |
| **Credibility gate + claim ledger** | Every artifact reference logged. Fresh-checkout reproduction (`verify_release.py`) for software deliverables. No contradicted claims, no stale proof, no missing limitations. | `build_claim_ledger.py`, credibility-gate skill |
| **Stitch gate** | Stitch-governed UI: runtime must be Stitch-faithful at the surface level, not just token-aligned. Token inheritance is not sufficient. | `check_stitch_gate.py` |
| **Visual gate** | `visual_reviewer` role pass for governed UI. Verifies composition anchors, route-family parity, page contracts, narrative structure — against actual runtime screenshots and walkthrough video, not filenames. | `check_visual_gate.py` |
| **Polish gate** | Clean-room artifact polish review must grade A on first impression, coherence, specificity, friction, edge finish, trust. | `check_polish_gate.py` |
| **Delivery gate** | Mechanical pre-delivery check that all required artifacts exist, all sub-gates passed, and the verification profile matches the deliverable type. | `check_delivery_gate.py` |
| **Final delivery review** | Final grade by the `gate_reviewer` role against the resolved brief stack, all prior gate reports, and every deliverable. A required. Nothing ships below A. | inline gate review |

A failed gate doesn't pass the work and doesn't quietly downgrade the criteria. It fails the ticket back to the executor with the gate's reason recorded. Only the gate's pass verdict produces forward motion.

```mermaid
flowchart TD
  P["Your Prompt"] --> C["Project Contract<br/>(mission map + proof strategy)"]
  C --> BG{"Brief Gate<br/>(gate_reviewer, A required)"}
  BG -->|fail| C
  BG -->|pass| T["Phases / Waves / Tickets"]
  T --> A["Executor Agents<br/>(routed by task_type)"]
  A --> BPF["Build-Prove-Fix Loop<br/>(verification manifest)"]
  BPF --> PG{"Phase Gate<br/>(gate_reviewer, A required)"}
  PG -->|fail| A
  PG -->|pass| QC["QC + Visual + Stitch"]
  QC --> M{"Mission Completion<br/>+ Credibility + Polish"}
  M -->|fail| A
  M -->|pass| D{"Delivery Gate<br/>+ Final Review (gate_reviewer)"}
  D -->|fail| A
  D -->|pass| F["Shipped"]
```

---

## Recovery

The platform assumes interruption is normal.

Every meaningful state change writes a checkpoint to disk: ticket frontmatter, work logs, `data/control-plane/` ledgers, evidence manifests, brief and gate reports, `ORCH-CHECKPOINT` entries in the project log. An executor can disappear mid-task and the next cycle answers:

- What was being attempted?
- What changed?
- What evidence exists?
- What gate failed?
- What is the next safe action?

A 45-minute executor session that times out without checkpointing has wasted that work. The orchestrator enforces checkpoints after every major step and on session start checks for a recent `ORCH-CHECKPOINT` to skip orientation entirely (saves ~17-24K tokens per resume).

The orchestrator's 20-iteration safety stop fires only after 20 consecutive iterations *without progress* — a stuck-state escape hatch, not a session length cap. Productive runs span hundreds of iterations across days.

Per-project derived context (`current-context.md`, `artifact-index.yaml`, image/video evidence indexes) regenerates from canonical files via `build_project_context.py` and friends. The markdown is truth; derived files are caches.

---

## Routing

The system has two execution modes. Both fully run the gate stack. The difference is the kind of independence at gate time: cross-model in `normal`, cross-context (fresh subagent on the host) in `chat_native`.

### `chat_native` (default — single host)

Everything — orchestrator, executors, gate reviewers — runs on whichever CLI is hosting the chat. Detection: explicit `host_agent` in `platform.md` → `CLAUDECODE` / `CODEX_HOME` env var → defaults to claude. **This is not a degraded mode.** Most users run inside one CLI; the system is designed to run end-to-end on a single host.

**You still get cross-context verification.** Every gate spawns a fresh subagent with a clean-room prompt and no build-phase memory. That's most of the value of the gate stack — catching false-completion, stale citations, scope drift — and it works on a single host. The hierarchy is:

> **cross-model > cross-context > inline.** Single-host mode loses cross-model but keeps cross-context.

### `normal` (opt-in — cross-model upgrade)

Set `agent_mode: normal` in `vault/config/platform.md` when both Claude and Codex are configured. The runtime routes by `task_type`:

| Task type | Routed agent | Why |
|-----------|--------------|-----|
| `orchestration`, `visual_review` | Claude | Control-plane judgment, design taste, multimodal review |
| `code_build`, `code_fix`, `code_review` | Codex | Implementation, debugging, refactors |
| `creative_brief`, `quality_check`, `artifact_polish_review` | Codex | Structured review with strict rubrics |
| `project_replan`, `plan_rebaseline`, `roadmap_reconciliation` | Codex | Deterministic plan edits |
| `stress_test`, `adversarial_probe` | Codex | Clean-room reviewer with no build-phase context |
| `credibility_gate` | Codex | Mechanical evidence audit |
| `artifact_cleanup`, `receipt_cleanup`, `docs_cleanup` | Codex | Bounded narrow lanes |

This adds genuine independence to gate reviews — different model, different training data, different failure modes — on top of the cross-context property you already had. Recommended when both CLIs are available.

### Explicit overrides

`claude_fallback` and `codex_fallback` route ALL work to the named agent regardless of host detection. Useful when one CLI breaks mid-run on a `normal`-mode setup.

### Semantic `--force-agent` roles

Gate prompts in `skills/orchestrator.md` use role names instead of model names so the skill stays mode-agnostic. Two roles, resolved by the runtime per-mode:

- `gate_reviewer` — cross-model reviewer for code/proof/credibility gates (→ codex in `normal`, host in `chat_native`).
- `visual_reviewer` — multimodal/taste reviewer for visual gates (→ claude in `normal`, host in `chat_native`).

The runtime emits `RUNTIME-ROUTING:` stderr log lines whenever a role is resolved, so you can audit substitutions in any run.

### Recommended setup (when budget allows)

Claude Max + ChatGPT Pro, both running, `agent_mode: normal`. The cross-model gate pattern (Claude builds → Codex reviews, or Codex builds → Claude judges visually) is the strongest configuration — but `chat_native` on a single host is fully supported and ships as the default.

---

## Self-Extending

When the system needs a tool it doesn't have, it doesn't say "I can't." It uses a 4-tier capability sourcing cascade:

1. **Skills marketplace** — `npx skills search` for pre-built skills.
2. **GitHub + MCP registries** — WebSearch for existing MCP servers.
3. **Internal archive** — `vault/archive/` of sanitized capabilities from prior projects.
4. **Build from scratch** — `build-mcp-server` writes Python MCP servers; `build-skill` writes new agent skills.

Every successful sourcing runs `archive-capability` to sanitize and save the result. The archive compounds across projects: each new build leaves the next one faster.

**Bundled MCPs** under `vault/clients/_platform/mcps/`:

- **`spending`** — agent budget caps with daily/monthly limits (wallet protection).
- **`stripe`** — optional payment rail with restricted API key.
- Third-party API wrappers: `calendar`, `charity`, `color-scheme`, `computer-use`, `eventbrite`, `financial-datasets`, `google-maps`, `google-search-console`, `image-compare`, `imagegen`, `mlx-whisper`, `sec-edgar`, `semantic-search`, `webflow`.

**The boundary:** alternate paths must still respect safety gates, legal/compliance rules, and admin approval. "Find another way" means creative problem-solving, not bypassing security.

---

## Workspace Isolation

Each project gets its own workspace under `vault/clients/{slug}/`:

- Isolated tickets, projects, decisions, lessons, snapshots.
- Client-scoped ticket counter.
- Workspace-specific MCPs and skills.
- A `config.md` with profile, ToS status, payment status, and budget.

Agents working on workspace A cannot read or write to workspace B. Platform-level work (e.g., system marketing, internal tools) lives at `vault/projects/`.

**Practice mode** (`is_practice: true` in client config) is a sandboxed lane for testing capabilities without external side effects: no outbound messages, no GitHub pushes, no real client contamination, no new tool sourcing. The full quality pipeline runs through artifact polish review; final Codex grade replaces client acceptance.

---

## Quality Bar

Most agent frameworks hide behind "high quality." ULTRAPROJECT names the bar — every brief is graded against named reference points researched live by the brief author:

- **Dashboards & internal tools** — Stripe Dashboard, Linear, Grafana, Datadog. Information density without clutter, semantic color, real interaction states.
- **Public web & landing pages** — Stripe.com, Vercel, Linear, Notion. Strong narrative structure, defined visual quality bar, composition anchors.
- **Decks & slides** — Apple keynotes, Sequoia template, TED. Typographic discipline, paced reveal, one idea per slide.
- **Reports & writing** — McKinsey, The Economist, FiveThirtyEight. Specific evidence, no consultant filler, executive summary that stands alone.
- **Games** — DOOM (2016), Half-Life 2, Hades, BG3. Weapon feel, AI behavior, lighting, polish in every interaction.
- **Brand identity** — Pentagram, Collins, Wolff Olins. System thinking, applications across touchpoints.

Every artifact passes a polish review against a universal consumption rubric (first impression, coherence, specificity, friction, edge finish, trust, delta quality) before it can close.

---

## A Note on Cost

ULTRAPROJECT optimizes for output quality, not LLM call count. Real projects stack many model calls per ticket between build, review, and the gate stack. Prompts pass full brief stacks and evidence manifests. **Expect to burn a lot of tokens.**

**Recommended setup:** Claude Code on Claude Max + Codex on ChatGPT Pro. The role split:

- **Claude →** orchestration, control-plane decisions, design judgment, narrative work, visual review.
- **Codex →** code build, debugging, test generation, refactors, gate reviews, drift detection, premium delivery review.

Routing rules live in `vault/config/platform.md` as plain YAML. Rebalance by hand, or just ask whichever coding agent you're already using ("update `vault/config/platform.md` to send all `code_review` tasks to Codex") and it'll do it for you.

Lower-tier plans will hit rate limits on real multi-day projects, which interrupts the walk-away promise. If you run with API-key auth instead of a subscription plan, real projects move real money — same advice applies: budget for it.

---

## Built With ULTRAPROJECT

The largest project built end-to-end through ULTRAPROJECT to date: a production-grade cross-platform database client (Tauri v2 + React 19 + Rust) with first-class PostgreSQL, SQLite, DuckDB, and CSV/XLSX support, plus enterprise security features.

**From a single prompt: ~6 days across ~200 tickets** — **~130,000 lines** of TypeScript (71K), Rust (35K), and Python (3K), plus configs and supporting code.

---

## What's Included

**System prompts and operating instructions:**
- `SYSTEM.md` — system prompt every agent reads first.
- `CLAUDE.md` — build instructions for new sessions.
- `AGENTS.md` — agent role definitions.
- `vault/SCHEMA.md` — markdown/frontmatter schema for project memory.

**Skills (`skills/`)** — ~30 role and workflow prompts:
- Core loop: `orchestrator`, `create-project`, `project-plan`, `gather-context`, `sync-context`, `vault-status`.
- Quality pipeline: `creative-brief`, `self-review`, `quality-check`, `artifact-polish-review`, `credibility-gate`, `deliverable-standards`.
- Capability sourcing: `source-capability`, `build-mcp-server`, `build-skill`, `register-mcp`, `test-mcp-server`, `archive-capability`.
- Institutional knowledge: `archive-project`, `match-playbooks`, `consolidate-lessons`, `post-delivery-review`, `meta-improvement`.
- Specialized: `deep-execute`, `test-manifest`, `build-remotion-video`, `source-audio`, `delete-client-data`.

**Scripts (`scripts/`)** — ~50 Python helpers:
- The 13 named gates above.
- Routing runtime: `agent_runtime.py` (spawn-task, run-task, ensure-stitch-auth, executor metering).
- Project context: `build_project_context.py`, `refresh_project_text_embeddings.py`, `refresh_project_image_embeddings.py`, `refresh_project_video_embeddings.py`, `refresh_project_code_index.py`.
- Evidence: `build_review_pack.py`, `build_claim_ledger.py`, `capture_walkthrough_video.py`, `ensure_qc_walkthrough.py`, `verify_release.py`.
- Search & retrieval: `index_vault.py`, `index_media.py`, `search_media.py`, `search_project_hybrid.py`, `project_text_retrieval.py`.
- Mode control: `set_agent_mode.py`, `set_claude_availability.py`.

**Vault (`vault/`)** — shared markdown memory:
- `clients/_template/` — workspace skeleton.
- `clients/_platform/mcps/` — 16 bundled MCP servers (see [Self-Extending](#self-extending)).
- `archive/` — sanitized reusable capabilities and de-identified playbooks.
- `config/platform.md` — sanitized routing table and quality contract.

**Tests (`tests/`)** — 35+ regression tests for routing, gates, evidence requirements, and project state.

**Hooks (`.claude/hooks/`)** — runtime guardrails: shell safety, path restrictions, audit logging, verification-first behavior.

**Tools (`tools/stitch-mcp-proxy/`)** — local Stitch MCP proxy scaffold.

**Docs (`docs/`)** — [ARCHITECTURE](docs/ARCHITECTURE.md), [QUICKSTART](docs/QUICKSTART.md), [SETUP](docs/SETUP.md).

---

## Project Status

Early release. The platform works end-to-end and real projects ship through it, but it isn't battle-tested across every environment yet. The test suite verifies the gate mechanics (routing, evidence requirements, ticket state) — not run-level reliability, which only usage proves out. Rough edges expected. Released under [Apache 2.0](LICENSE) — fork it, modify it, ship things with it (the patent grant in Apache 2.0 protects everyone, yours and theirs). PRs, forks, and people doing genuinely weird things with it are all welcome — issues and PRs are reviewed on a best-effort basis.

If you find a security issue, see [SECURITY.md](SECURITY.md).

## Responsible Use

This system spawns AI agents that execute shell commands, read and write files, and (when configured) make outbound API calls. Treat that surface seriously:

- **The Stripe rail ships disabled and should stay that way in this release.** `pricing.require_payment` defaults to `false` and the optional Stripe MCP is not wired into `.mcp.json` by default. Until this version has more usage and external security review, do not enable autonomous Stripe charges against live cards. Restricted keys help, but a fresh-release autonomous payment rail is not the place to test the trust model.
- Review `.env.example` and `.mcp.example.json` before adding credentials. Never commit `.env` or a live `.mcp.json`.
- Use restricted-mode API keys wherever the provider supports them. The included MCPs assume least-privilege keys.
- The `.claude/hooks/` directory is the runtime guardrail layer (shell safety, path restrictions, audit logging). Read it before disabling anything.
- The `spending` MCP enforces daily/monthly budget caps for any agent that touches paid APIs. Configure it.
- External code from client repos is treated as untrusted data — read-only analysis only, no install hooks or scripts run.
- Respect the terms of every model, API, and data provider you connect — rate limits, attribution, allowed use cases.

## License

[Apache 2.0](LICENSE) — do whatever you want, just keep the copyright notice and the `NOTICE` file.
