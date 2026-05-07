<div align="center">

# OneShot

### One prompt. Full delivery.

OneShot is a Claude plugin plus a local project folder that turns one big request into a finished project. You open the OneShot folder, type `/oneshot`, describe what you want, and Claude keeps working until it's done — or until it needs a decision only you can make.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-v2.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/hero-light.png">
  <img alt="OneShot" src="docs/assets/hero-v2.png">
</picture>

</div>

---

## What it does

A normal Claude chat answers one question. OneShot keeps Claude going through the whole job — making the files, running the checks, fixing what broke, verifying the result. It can run for an hour, a day, or across resumed sessions.

It pauses and asks you when it needs a password, system access, a payment, or a real human decision. Otherwise it keeps working.

The OneShot folder is the engine — it contains the instructions, vault, project records, tickets, and proof trail. The Claude plugin is the clean `/oneshot` button that starts the engine.

## Install

You need two things: the **OneShot folder** (the engine) and the **Claude plugin** (the `/oneshot` button).

1. **Get the OneShot folder.** Clone the repo, or download the source zip from the [latest release](https://github.com/oneshot-repo/OneShot/releases/tag/v0.1.0) and unzip it somewhere you can keep it (e.g. `~/Documents/OneShot`).
2. **Install the Claude plugin.** From the same release, download `oneshot-claude-plugin-0.1.0.plugin`. In Claude Desktop, open plugin settings, upload the file, and enable OneShot.
3. **Start a job.** Open Claude in the OneShot folder, type `/oneshot`, and paste your request.

> The `.zip` in the release is the same plugin in a different wrapper. Only use it if your system blocks `.plugin` files.

## How to use it

The simplest version:

```text
/oneshot build a small habit-tracking app I can run locally
```

For real results, tell Claude five things:

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

## Using Codex (optional)

Claude Desktop is the smoother experience and the recommended path. If you'd rather use Codex, open Codex in the OneShot folder and ask:

```text
Run a OneShot for this:

[your prompt]
```

Quality varies more than with Claude — keep that in mind for long jobs.

## What to expect

- **Big asks take real time.** Hours, sometimes longer.
- **It can't bypass logins or payments.** It pauses and asks.
- **If a session ends**, reopen Claude in the OneShot folder and tell it to resume the active OneShot.
- **It needs the OneShot folder.** The plugin starts the workflow; the folder stores the workflow.

## Safety

OneShot lets Claude read your files, edit them, run commands, and use connected tools. Only point it at folders you're comfortable with that.

Don't paste secrets or credentials into prompts.

## More

- [Architecture](docs/ARCHITECTURE.md) — how OneShot works under the hood

## License

[Apache 2.0](LICENSE). OneShot is derived from the project listed in [`NOTICE`](NOTICE).

Created by [Michael Zola](https://www.linkedin.com/in/michaeljzola/)
