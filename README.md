<div align="center">

# OneShot

### One prompt. Full delivery.

OneShot is a chat-native project delivery system for jobs too big for one chat. You give it one prompt, and a coding agent keeps working until the job is finished.

Built for Claude Desktop. Also works with Codex or any capable coding agent.

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

The OneShot folder is the engine — it contains the instructions, vault, project records, tickets, and proof trail. The Claude plugin is the cleanest interface, but the engine is just a folder that a capable coding agent can run from.

## Install

You need the **OneShot folder** and a coding agent. Claude Desktop with the plugin is the smoothest path, but the plugin is not required if you want to run OneShot from Codex or another capable coding agent.

### 1. Get the OneShot folder

Clone the repo:

```bash
git clone https://github.com/oneshot-repo/OneShot.git ~/Documents/OneShot
```

Or download the source zip from the [latest release](https://github.com/oneshot-repo/OneShot/releases/tag/v0.1.0) and unzip it somewhere you can keep it.

### 2. Choose how to run it

#### Option A: Claude Desktop, recommended

Install the plugin if you want the `/oneshot` command:

1. Download `oneshot-claude-plugin-0.1.0.plugin` from the [latest release](https://github.com/oneshot-repo/OneShot/releases/tag/v0.1.0).
2. In Claude Desktop, open plugin settings, upload the file, and enable OneShot.
3. Open Claude Desktop in the OneShot folder.
4. Type `/oneshot` and paste your request.

#### Option B: Codex or another coding agent

You do not need the Claude plugin for this path. Open your coding agent in the OneShot folder and use this full starter prompt:

```text
Oneshot this:

[Your prompt, specs, project, goal, etc.]

Before starting, read SYSTEM.md and skills/orchestrator.md, especially the Critical Rules block at the top of orchestrator.md. Follow the orchestrator skill literally. Treat the files in this repo as the source of truth, not chat memory.

If details are missing, make reasonable implementation assumptions, record them in the project file, and keep going.

Do not reduce scope, quality, proof requirements, user-facing polish, or delivery obligations unless I explicitly approve that change. Do not reinterpret the request as a prototype, draft, MVP, plan, scaffold, partial implementation, or "best effort" unless those words are in my request.

When ambiguity exists, do not choose the smaller or easier interpretation. Preserve the full stated goal and deliver the most complete version consistent with my request. If an ambiguity affects scope, quality, proof, polish, or delivery, record the assumption and continue on the path that maintains or increases the requested outcome. Tickets and amendments may clarify or add work; they may not reduce, defer, or downgrade the requested outcome without my explicit approval.

Work until the project is delivered: all acceptance criteria satisfied, required proof gathered, final review passed, and deliverables handed off. Stop only if I explicitly pause/kill the run, or if every executable path is blocked by a legal, credential, approval, physical-world, or safety constraint. In that case, write a complete blocker report listing every blocked path and exactly what is needed to unblock each one.
```

**Platform note:** OneShot is optimized for macOS today. On Windows, install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install), open Ubuntu, and run the steps above from inside WSL. Claude Desktop can open WSL folders via `\\wsl$\` paths. OneShot's engine is cross-platform, but a few skills assume Unix tools, so WSL is the smoother route. If you want a native Windows workflow, ask your coding agent to help adapt the setup for Windows paths and shell commands.

## How to use it

The simplest version in Claude Desktop:

```text
/oneshot build a small habit-tracking app I can run locally
```

Without the Claude plugin, use the full `Oneshot this:` starter prompt above from the OneShot folder.

For real results, tell the agent five things:

- **Goal** — what you actually want
- **Audience** — who's going to use, judge, or pay for it
- **Done means** — the specific finish line
- **Avoid** — anything off-limits, lazy, or against your taste
- **Proof** — what you want to see before it hands the work back

The prompts below are the kind of thing OneShot is built for — multi-day jobs that a normal chat would give up on by paragraph two. Steal liberally.

---

### Build a real native app

```text
/oneshot build a polished cross-platform desktop journaling app called "Trace."

Goal: a serious native journaling app for Mac, Windows, and Linux that feels like premium software, not a webview wrapper. Daily entries, tagging, full-text search, encrypted local storage, optional Dropbox or iCloud sync, a markdown editor with live preview, image and audio attachments, mood tracking with weekly charts, and a "year in review" generator that produces a printable PDF.

Audience: writers, founders, and designers who already pay for journaling apps and can immediately tell the difference between cheap and considered software.

Done means: signed installers for Mac, Windows, and Linux; an onboarding flow; a settings panel; OS-conventional shortcuts; dark and light themes with accessible color choices; offline-first behavior; full keyboard navigation; telemetry off by default; a README of 6+ pages with screenshots, architectural reasoning, and a security section explaining the encryption choices.

Avoid: Electron unless deliberately justified, paid APIs, AI features bolted into the editor, gradient-heavy "AI app" design, login walls on first launch, and analytics that fire before opt-in.

Proof: run the app locally and capture screenshots of the four core flows (compose, search, sync setup, year-in-review export), include build artifacts in the release, and produce a verification report listing every command, test, and manual check used to confirm the build is real.
```

---

### Ship a browser game with taste

```text
/oneshot build a polished browser game called "Lighthouse" — a 2D atmospheric exploration game playable in any modern browser, no install required.

Goal: a single-player game where you play a young lighthouse keeper on a remote coast over the course of a year. Real-time day/night cycle, weather system, diary mechanic, a small cast of NPCs who arrive by boat, four storylines that interweave, a soundtrack of ambient piano and ocean recordings, and a final ending sequence that responds to the choices the player made.

Audience: people who liked Firewatch, A Short Hike, and Dredge — players who want a calm, well-written game they can finish in an evening with no combat and no scoreboards.

Done means: a fully playable build hosted from a static folder, runs in Chrome / Safari / Firefox / mobile; save and load works; all four storylines are reachable; all art and audio are original or properly licensed; an itch.io-ready zip; a README with controls, a one-paragraph artistic intent, and an in-game credits page.

Avoid: pay-to-win mechanics, ads, social-login walls, third-party tracking, uncredited AI-generated art, and any combat. The tone is contemplative, not competitive.

Proof: run the game locally and screenshot the title scene, two key story beats, the diary screen, and the ending. Capture a 90-second walkthrough video. Include playtest notes from a complete run-through with timestamps and observations on pacing.
```

---

### Deliver a real strategic research report

```text
/oneshot research and write a 60+ page strategic report and deliver it as a finished, publishable artifact.

Goal: a report titled "The Coming Decade of Personal Robotics: 2026–2036." Cover the technical landscape (humanoid platforms, dexterous manipulation, perception, on-device AI, battery and actuator limits), the economic landscape (funding, key players, revenue models, total cost of ownership), the regulatory landscape (US, EU, China, Japan), the labor and ethical landscape (jobs displaced, jobs created, accident liability), and a 10-year forecast with three scenarios (slow, base, fast).

Audience: a senior partner at a generalist VC firm briefing their LPs. They don't need to be told what a humanoid robot is. They do need to be told which eight names actually matter and why.

Done means: a fully written report in PDF and HTML; a 2-page executive summary; a sourced bibliography with access dates; charts rebuilt from primary data (not screenshotted from press); a glossary of any term defined more than twice; and a one-page "what we got wrong if this ages badly" section listing the most fragile assumptions in the report.

Avoid: weasel words, fabricated statistics, citations to AI-generated sources, "according to experts" without naming experts, breathless valuations, and any quote that can't be traced to a specific publication and date.

Proof: every numerical claim links to a primary source. The bibliography includes access dates. Include a verification log showing how each chart was rebuilt from underlying data. Run a self-review pass and document the 10 weakest claims with a note on why they were kept or revised.
```

---

### Modernize an old codebase without breaking it

```text
/oneshot take this old web codebase and ship a modernized version that actually runs in production.

Goal: take this jQuery + PHP 5 + MySQL legacy admin tool and produce a working modern rewrite — TypeScript on the frontend with React 19, a Hono or Fastify backend in Node, Postgres with migrations, full type safety end-to-end, an OpenAPI spec, and a real test suite. Every existing feature must be preserved bit-for-bit. Anything that looks like a bug in the original should be flagged, not silently "fixed."

Audience: the original maintainer of the legacy app, who is mistrustful of rewrites because the last two attempts broke production. They will read the diff.

Done means: every page in the legacy app has a 1:1 working equivalent in the new app; a feature-parity matrix mapping every old route to the new one; a migration script for existing data; a docker-compose for local development; CI that runs lint + typecheck + tests; a CHANGELOG documenting every behavioral difference (intentional or discovered); and a deployment guide.

Avoid: changing UX while modernizing, dropping features without explicit approval, bleeding-edge libraries with low maturity, "while we're here" refactors of unrelated systems, and any silent behavior changes.

Proof: run the legacy app and the new app side by side. Walk every route in both. Produce a side-by-side screenshot comparison of the 20 most-used pages. Run the data migration on a copy of the production DB and diff the two databases. Record a video walkthrough of the parity check.
```

---

### Build a complete self-paced technical course

```text
/oneshot build a complete self-paced course called "Postgres for Working Engineers."

Goal: an end-to-end 8-module written course aimed at backend engineers with 2–6 years of experience who use Postgres every day but never went deep. Cover query planner internals, indexing for real workloads, locking, MVCC and bloat, partitioning, replication, JSONB patterns, and operating Postgres in production. Each module includes a 30–60 minute reading, hands-on exercises with a docker-compose'd Postgres, and a graded self-check with answer keys.

Audience: engineers who already know SQL and can run a join, but freeze when their staging DB gets a query that takes 40 seconds and they don't know how to read EXPLAIN ANALYZE.

Done means: 8 written modules in markdown; a running docker-compose Postgres environment with seed data large enough that bad queries actually hurt; exercises that produce verifiable artifacts; a published static HTML version of the course; printable PDF version; and a 2-page "what to read after this" page pointing to specific chapters of specific books.

Avoid: re-explaining basic SQL, marketing tone, "the Postgres docs say…" without a deeper take, screenshot-only exercises, and any exercise that doesn't have a verifiable answer.

Proof: run every exercise end-to-end on a fresh docker-compose stack and commit the expected output. Record a short video of one exercise being completed cold. Run a self-review pass through every module and write a critique of the 5 weakest paragraphs in each one before final delivery.
```

## What to expect

- **Big asks take real time.** Hours, sometimes longer.
- **It can use a lot of tokens.** OneShot keeps context, reviews its work, runs checks, and revises until the job is actually done; serious jobs can consume substantially more tokens than a normal chat.
- **It can't bypass logins or payments.** It pauses and asks.
- **If a session ends**, reopen your agent in the OneShot folder and tell it to resume the active OneShot.
- **It needs the OneShot folder.** The folder stores the workflow; the Claude plugin is only one way to start it.

## Safety

OneShot is powerful local automation. Through your active coding agent, it can read files, edit them, run shell commands, use connected tools, and keep working through long autonomous sessions.

Use it in an environment you control. Keep secrets and credentials out of prompts, scope connected API keys to least privilege, and use a dedicated user account or VM for risky or untrusted work.

## More

- [Architecture](docs/ARCHITECTURE.md) — how OneShot works under the hood

## License

[Apache 2.0](LICENSE). OneShot — formerly ULTRAPROMPT — is derived from the project listed in [`NOTICE`](NOTICE).

Created by [Michael Zola](https://www.linkedin.com/in/michaeljzola/)
