---
type: skill
name: deliverable-standards
description: Professional output standards per deliverable type — applied automatically by self-review and QC without needing per-project specification
inputs: []
---

# Deliverable Standards

**The quality bar is ENTERPRISE, PRODUCTION GRADE.** Every deliverable must look and feel like it was produced by a top-tier agency for a Fortune 500 client. Not "good for AI." Not "it works." Not "the data is correct." World-class.

**The creative brief defines WHAT to build. This file defines HOW GOOD the baseline must be.**

**Reference standard:** Think Stripe's dashboard, Linear's UI, Apple's keynote decks, Bloomberg's data visualizations, Airbnb's design system. If your output wouldn't look at home next to these, it's not done yet.

**Time and complexity are not excuses.** If producing enterprise-grade output requires 50 tickets across 5 phases with iterative refinement, do that. If it requires sourcing new tools, building new MCPs, or learning new techniques, do that. Quality is the constraint that never bends. Speed is the variable.

**The most common failure mode is "technically correct but visually amateur."** Data is accurate, code works, brief is met — but the output LOOKS like AI made it. Generic fonts, basic tables, flat colors, no visual rhythm, no design system, no attention to craft. This is an F, not an A-. The bar is not "does it function" — it's "would a discerning client pay premium rates for this without hesitation."

**Universal verification principle:** Every deliverable type has a proof-of-correctness method. "It looks right" is not proof. "It passed code review" is not proof. The only proof is execution: the build succeeded, the tests pass, the functional proof demonstrates the core workflow, and domain-specific claims are independently verified. The creative brief defines the specific verification protocol; this file defines the proof categories available for each deliverable type. If a deliverable ships without its proof-of-correctness method having been executed, it has not been verified — regardless of how many times someone read the source.

Self-review and quality-check MUST consult these standards for the relevant deliverable type. If a deliverable violates any standard below, it's a quality issue regardless of whether the brief mentioned it.

## Universal Consumption Review

Every client-consumed artifact must survive a clean-room consumption review after QC. This review is not asking "does it technically work?" It is asking "does it feel finished, credible, and intentional to a human seeing it fresh?"

The universal polish rubric is:

- **First Impression:** Does it look credible immediately, or does it feel generic / rough / incomplete?
- **Coherence:** Do the parts feel like one intentional artifact, or like assembled pieces?
- **Specificity:** Is it clearly for this project/client/use case, or could it be swapped with any generic output?
- **Friction:** Where would a real reviewer get confused, distrustful, stalled, or underwhelmed?
- **Edge Finish:** Dead space, placeholder copy, awkward states, thin sections, dead-end navigation, broken hierarchy, off-by-one layout issues, visual imbalance, or rough exports all count against polish.
- **Trust:** Does the artifact feel grounded, reviewable, and professionally presented?
- **Delta Quality:** For revisions, did it actually fix the rejected thing, or just move the surface area around?

Passing functional QC is necessary but not sufficient. A deliverable can be technically correct and still fail the consumption review if it feels unfinished, generic, or weak under human inspection.

## Data / CSV / Spreadsheet

**Formatting:**
- Currency columns: `$1,234,567.00` (dollar sign, thousands separator, 2 decimal places)
- Percentages: `45.2%` (with percent sign, 1 decimal place unless precision matters)
- Phone numbers: `(555) 123-4567` (standard US format, or international with country code)
- ZIP/postal codes: preserve leading zeros as strings, never as integers
- Dates: consistent ISO format `YYYY-MM-DD` unless client specifies otherwise
- Large numbers: thousands separators (`1,234,567` not `1234567`)
- Empty/null values: consistent representation (`N/A` or blank — never mixed)

**Structure:**
- Column headers: human-readable, Title Case (`Total Revenue` not `tot_rev` or `TOTAL_REVENUE`)
- Sort order: meaningful default (largest first for rankings, alphabetical for directories, chronological for timelines)
- No duplicate rows unless duplicates are meaningful
- Encoding: UTF-8 with BOM for Excel compatibility
- Line endings: CRLF for cross-platform compatibility

**Quality:**
- Spot-check the top 10 and bottom 10 rows for obvious errors
- Verify totals/aggregates if present
- Cross-reference a few rows against the source data
- No obviously stale or placeholder data

## Website / HTML (brochure sites, portfolios, landing pages)

**Note:** For JS-heavy web apps (React, Vue, dashboards, games-in-browser), the "Graceful degradation" rule is relaxed — these apps inherently require JS. All other standards still apply. Use the "Game / Interactive Application" section for browser-based games.

**Visual (enterprise grade — not "meets minimum"):**
- Distinctive design with a clear aesthetic point of view — not generic Bootstrap/Tailwind defaults
- Public-facing pages must make a product argument, not just present a feature inventory
- Generic SaaS landing-page patterns are a failure mode: card soup, weak hero copy, too many boxed sections, interchangeable gradients, and no trust/proof layer
- Intentional typography: display font + body font pairing, proper scale (not just "16px Arial everywhere")
- Color system with semantic meaning — primary, secondary, accent, success, warning, error, surface, text hierarchy. Not random colors.
- Spacing system — consistent scale (4/8/12/16/24/32/48/64px), not arbitrary padding
- Real imagery — sourced via stock-photo MCP or generated. No placeholder icons as the only visual content.
- Micro-interactions — hover states, transitions, focus indicators that feel intentional
- WCAG AA contrast minimum, but aim higher — design should feel effortless to read
- No horizontal scrolling at any viewport width
- Responsive at every width 375-1440px, not just 3 breakpoints

**Structure:**
- Semantic HTML (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`)
- For landing pages, homepages, pricing pages, and other public first-impression surfaces: clear narrative progression (hero → proof → explanation → strongest use cases → differentiation → CTA)
- Top-level nav surfaces such as Account, Settings, Billing, Profile, Dashboard, and Admin must expose a coherent page contract with multiple expected sections/states when appropriate
- Dangerous/destructive actions belong inside a clearly labeled danger zone, never as the entire top-level page unless the brief explicitly defines that product behavior
- All images have meaningful alt text
- All links work (no 404s, no placeholder hrefs)
- Forms have labels, validation, and clear error messages
- Page has a meaningful `<title>` and meta description

**Performance:**
- Images optimized (no 5MB PNGs for thumbnails)
- CSS and JS minified or at least not bloated
- External resources loaded from reliable CDNs with verified URLs
- Page loads in under 3 seconds on a reasonable connection

**Graceful degradation:**
- Content visible without JavaScript
- Page usable without CSS (content still readable)
- No critical functionality gated behind a JS framework loading

## PDF / Document / Report

**Layout:**
- Clear page hierarchy with headings and subheadings
- Consistent margins and spacing throughout
- Page numbers on multi-page documents
- Table of contents for documents over 5 pages

**Content:**
- No placeholder text (Lorem ipsum, [TBD], TODO)
- All data visualizations have labels, legends, and clear titles
- Citations/sources are linked or referenced
- Executive summary for documents over 3 pages

**Quality:**
- Proofread for obvious typos and grammar errors
- Consistent terminology throughout
- Figures and tables referenced in the text

## 3D Renders / Images

**Quality:**
- Minimum resolution: 1920x1080 for hero images, 800x600 for thumbnails
- Proper lighting (not flat, not blown out)
- No obvious clipping, z-fighting, or rendering artifacts
- Consistent style across a set of images

**Relevance:**
- Images depict the correct subject matter for the client's industry
- No reuse of assets from unrelated domains
- Style matches the creative brief's visual direction

## Video / Animation

**Quality:**
- Minimum 720p resolution, prefer 1080p
- Smooth frame rate (24fps minimum for animation)
- No audio glitches or sync issues (if audio present)
- Clean start and end (no abrupt cuts)
- Web-optimized encoding (H.264 with faststart for MP4)

## Email (client-facing)

**Formatting:**
- HTML formatted (never plain text for client deliveries)
- Branded header section
- Structured sections with clear headings
- Data in HTML tables, not raw text dumps
- AI disclosure footer properly styled
- Responsive (readable on mobile)

## Code / Scripts (when delivered to client)

**Quality:**
- Documented: clear comments explaining non-obvious logic
- Has a README or usage instructions
- Handles errors gracefully (doesn't crash on bad input)
- Has example usage or a `--help` flag
- No hardcoded paths or credentials

## Compiled Software / Desktop Application (Tauri, Electron, native, etc.)

**Build integrity:**
- Project builds from a clean checkout with documented commands (no undocumented manual steps)
- Build produces the expected artifacts (binary, installer, app bundle) at the expected paths
- Build completes with exit code 0 and no errors (warnings acceptable if documented)
- All dependencies resolve (no missing crates, packages, or modules)
- Cross-compilation targets (if specified) all build successfully

**Test coverage:**
- Test suite exists and runs to completion
- Zero test failures in the shipped build (flaky tests must be fixed or explicitly skipped with documented reason)
- Tests exercise core functionality (not just "1 test that imports the module")
- Integration tests verify that frontend and backend communicate correctly (for hybrid apps like Tauri/Electron)

**Runtime verification:**
- Application launches without crash on the target platform
- Main window renders with expected UI elements visible
- Core workflow completes end-to-end (not just "window opens" but "user can perform the primary task")
- No unhandled panics, uncaught exceptions, or error dialogs during normal operation
- Application exits cleanly (no zombie processes, no corrupted state)

**Packaging:**
- Installer or app bundle is properly signed (if targeting distribution)
- Application icon and metadata are set (not default/placeholder)
- README includes: system requirements, install instructions, build-from-source instructions
- License file present if using open-source dependencies

**Performance:**
- Cold start time measured and documented
- Memory usage under typical workload measured
- No memory leaks during sustained operation (measure RSS over 5 minutes of use)
- UI remains responsive during background operations (no freezing)

**Quality:**
- No hardcoded development paths, localhost URLs, or debug flags in release build
- Error messages are user-facing (not stack traces or panic messages)
- Logging is appropriate (not verbose debug output in release mode)
- Configuration is documented and uses sensible defaults

## Game / Interactive Application

**This is NOT a prototype checklist. Games ship finished or they don't ship.**

**Visual quality:**
- All geometry uses final textured models — no graybox, no CSG placeholders, no untextured surfaces in the final build
- Lighting creates atmosphere and mood — directional lights, shadows, ambient occlusion, emissive materials. Flat uniform lighting is a fail.
- VFX are present and polished — muzzle flash, impacts, particles, screen effects. If a weapon fires with no visual feedback, it's broken.
- UI/HUD is styled and readable — not default engine widgets. Consistent design language across all screens.
- Menus look designed — title screen, pause menu, settings, game over. Not placeholder text on a blank background.

**Audio:**
- Every interaction has audio feedback — weapons, footsteps, impacts, UI, ambient
- Audio is layered — not a single flat sound per action
- Music transitions between game states (menu, exploration, combat, victory, death)
- Surface-specific footsteps if the game has multiple surface types
- Silence at any point during normal gameplay is a bug

**Mechanics:**
- Core gameplay loop is complete and feels responsive — zero input lag, smooth camera
- AI behaves intelligently — uses cover, flanks, retreats, varies behavior by archetype
- Progression systems work end-to-end — start to finish, every encounter, clear win/lose states
- No softlocks, no sequence breaks, no dead ends
- Difficulty escalation is noticeable across encounters

**Polish:**
- No Z-fighting, no clipping, no floating objects, no invisible walls without visual cues
- Frame rate is stable throughout
- Camera doesn't clip through geometry
- Death/respawn cycle works cleanly
- All text is readable and properly positioned

## Dashboard / Data Visualization

**Think Bloomberg Terminal, Stripe Dashboard, Linear, Grafana — not HTML tables with borders.**

**Design:**
- Real design system — consistent spacing, type scale, color tokens, component patterns
- Dark and light themes that both look intentional (not just "invert the colors")
- Information hierarchy — the most important metric is the largest/most prominent element
- Cards/panels with proper elevation, spacing, and grouping by function
- Navigation that scales — sidebar, tabs, or breadcrumbs, not a flat page of everything

**Data visualization:**
- Charts use proper libraries or well-crafted SVG — not basic rectangles with text labels
- Every chart has: title, axis labels, legends, tooltips on hover, proper scales
- Color encodes meaning (green = positive, red = negative, blue = neutral) consistently
- Tufte principles: maximize data-ink ratio, no chartjunk, small multiples where appropriate
- Tables are styled with alternating rows, sticky headers, sortable columns, proper alignment (numbers right-aligned)
- Large numbers formatted with separators and appropriate precision

**Interactivity:**
- Filters, date ranges, search — dashboards are tools, not static pages
- Loading states for async data
- Keyboard shortcuts for power users
- Responsive — usable on tablet and mobile, not just desktop

**Data quality:**
- Real data from real sources (MCPs), not hardcoded sample data in the final version
- Timestamps showing when data was last refreshed
- Clear indication of data source and methodology

## API / MCP Server

**Quality:**
- All tools have docstrings
- Error responses are descriptive (not just "Error")
- Handles missing/invalid parameters gracefully
- Credentials read from environment variables
- Tested with [[test-mcp-server]] including artifact verification

## Critical Flow Verification (MANDATORY for interactive software deliverables)

**Unit tests verify components. Critical flow tests verify the product.** A deliverable where every unit test passes but the core user flow is broken has not been tested. This section requires end-to-end flow verification against the ACTUAL running application — not mocks, not a dev server without the backend, not individual components in isolation.

This section applies to interactive software deliverables: desktop apps, web apps, APIs, MCP servers, CLIs, games. For non-interactive deliverables (documents, data, reports, presentations), end-to-end verification is handled by the Verification Protocol and Enterprise Quality Gate sections below.

### What is a Critical Flow?

A critical flow is a multi-step user journey that exercises the product end-to-end. It starts with a user action and verifies every downstream effect. The flow fails if ANY step in the chain produces an unexpected result — even if each component works in isolation.

**Example (database client):** "Connect to database" is NOT a critical flow. "Connect to database → sidebar shows saved connection → status bar shows active connection → schema explorer loads tables → clicking a table shows columns" IS a critical flow. Every downstream effect is verified.

### Requirements

1. **The creative brief defines critical flows in its Functional Proof table.** 5-10 flows covering all core user journeys. If the brief doesn't define them, the project plan phase must add them before build work starts. Phase gate runtime verification executes these flows as regression anchors.

2. **Critical flows must be tested against the REAL running deliverable.** The application must be built, launched, and interacted with through the same interface a user would use. Mocked IPC boundaries, dev servers without the backend, or component-level rendering do not satisfy this requirement.

3. **Each flow must assert every downstream effect.** "Connect succeeded" is not sufficient. Every UI element, state change, and data propagation that should occur must be explicitly checked.

4. **Use the right tool for each platform:**

   | Platform | Flow Verification Tool | Notes |
   |----------|----------------------|-------|
   | **Tauri (Windows/Linux)** | `tauri-driver` (native WebDriver support) | Official Tauri WebDriver. Tests real IPC, real Rust backend, real state. |
   | **Tauri (macOS)** | `tauri-webdriver` (community, danielraffel/tauri-webdriver) or Computer Use MCP | macOS has no native WKWebView WebDriver. Use the community `tauri-webdriver` crate if available. If not, fall back to Computer Use MCP. Playwright against the Vite dev server covers the web layer but NOT Tauri IPC — acceptable only for UI-only verification with an explicit INFRASTRUCTURE-DEPENDENT annotation for IPC-dependent flows. |
   | **Electron** | Playwright Electron API (`electron.launch()`) | Playwright connects directly to the Electron process. |
   | **Web app** | Playwright against the built/deployed app | Not the dev server — the production build with real backend. |
   | **CLI tool** | Shell script running commands in sequence | Assert stdout, stderr, exit codes, and produced artifacts for each step. |
   | **API** | HTTP client (curl, requests, httpx) | Hit the running server. Assert response bodies, status codes, headers, and state changes. |
   | **MCP server** | `[[test-mcp-server]]` protocol + MCP client | Use the existing MCP test protocol. Assert tool responses and side effects. |
   | **Game** | Platform-specific automation or Computer Use | Computer Use is acceptable for games where no programmatic UI automation exists. |

5. **Critical flow proof results are phase gate evidence.** Every build phase runtime verification must include critical flow proof results. A phase where all unit tests pass but critical flows were not executed does not pass the gate.

6. **Failures in critical flows block delivery.** A critical flow failure is a HIGH severity finding. The deliverable does not ship until all defined critical flows pass.

7. **Interactive browser/native flows need motion evidence, not screenshots alone.** For web apps, dashboards, desktop apps, games, and other interactive visual software, QC must capture a short walkthrough video of at least one canonical flow and cite the filename in the report. Screenshots prove rendered state; walkthrough video proves flow continuity, transitions, and interaction quality.

### Relationship to Other Standards

- **Unit/integration tests** (Test coverage section): verify components work individually
- **Critical flow tests** (this section): verify components work together as a product
- **Ground truth validation** (Enterprise Quality Gate §1): verify correctness against external references
- **Admin usability review** (Phase 9): catches subjective quality and feel that automated flows can't measure

All four layers are required. They are not substitutes for each other.

---

## Enterprise Quality Gate (MANDATORY for all client deliverables)

The per-type standards above define craft. This section defines trust. A deliverable can be beautifully crafted and still not enterprise-grade if it hasn't been validated against reality. These six requirements apply to every client deliverable regardless of type.

### 1. Ground Truth Validation

**The deliverable's output must be verified against an independent reference — not just checked for internal consistency.**

| Deliverable Type | Ground Truth Source |
|-----------------|-------------------|
| Code / CLI tool | Compare key outputs against a reference tool (e.g., entity counts against Sourcegraph, AST output against pyright, metrics against SonarQube). Document which reference was used and any deltas. If no reference tool exists for a novel domain, define a hand-verified golden dataset as ground truth. |
| Website / web app | Validate against WCAG AA standards (AAA where feasible), Lighthouse 90+ scores, and at least one competitor site as a design benchmark. |
| Data / CSV / spreadsheet | Compare a random sample (minimum 50 rows or 5%) against the original source. Document match rate per column. |
| PDF / document / report | Cross-reference cited statistics against their original sources. Verify calculations and aggregates independently. |
| Research / analysis | Cross-reference key claims against at least 3 independent published sources. Flag any claim with only a single source. |
| Dashboard / visualization | Verify displayed numbers against raw data queries. Every chart value must trace to a source query that produces the same number. |
| API / MCP server | Compare responses against the upstream API's own documentation or reference implementation. |
| 3D renders / images | Compare against reference images from the creative brief. Verify scene composition, lighting, and subject match the spec. |
| Video / animation | Verify runtime, resolution, and codec against spec. Compare key frames against storyboard or brief. |
| Game / interactive app | Compare mechanics against the creative brief's spec. Verify physics, scoring, and progression math independently. |
| Client-facing communication draft | Verify professional formatting and required disclosure language. Compare against the brief's content requirements. |

**The creative brief must define ground truth targets.** If the brief doesn't specify what reference to validate against, QC must flag this as a gap before delivery. For novel tools with no existing reference implementation, the brief must define a hand-verified golden dataset or expected output specification.

### 2. Breadth Testing

**Testing against one input is a demo. Testing against many varied inputs is validation.**

| Deliverable Type | Minimum Breadth |
|-----------------|----------------|
| Code / CLI tool | 5+ varied real-world inputs (different sizes, languages, edge cases). At least one input at 10x the expected scale. |
| Website / web app | 5+ browsers/viewport widths. Test with slow network (3G throttle) and screen reader. For static sites: also test with disabled JS. For JS-heavy apps (React, Vue, dashboards): skip disabled-JS test per the base website standards exemption. |
| Data / CSV / spreadsheet | 3+ source datasets of different sizes and formats. Test with missing data, encoding issues, and edge-case values. |
| PDF / document / report | Review across 2+ readers (Preview, Chrome PDF viewer, Adobe). Verify cross-references, page links, and table of contents. |
| Research / analysis | Sources from 3+ independent publishers/databases. Not 5 articles from the same author. |
| Dashboard / visualization | Test with empty data, single-row data, and max-scale data. Verify all filters, date ranges, and interactive controls. |
| API / MCP server | 10+ varied requests including malformed input, missing params, rate limiting, and timeout scenarios. |
| 3D renders / images | Render at 2+ resolutions. Verify from 3+ camera angles if applicable. |
| Video / animation | Playback test on 2+ players/browsers. Verify codec compatibility. |
| Game / interactive app | Full playthrough at minimum 3 different player strategies/paths. Test every mechanic, not just the happy path. |
| Email (client-facing) | Render test across 3+ email clients. Test with images disabled. |

### 3. Documented Failure Modes

**Every deliverable must include a "Known Limitations" section documenting what happens when things go wrong.**

This goes in the README (for code), the delivery email (for all types), or a dedicated `LIMITATIONS.md`. It must answer:
- What inputs will break it? (e.g., "Files over 1M LOC may exceed memory on 8GB machines")
- What does it do when it fails? (crash, partial result, error message?)
- What edge cases are known but unhandled? (e.g., "Dynamic imports via `importlib` are not tracked")
- What are the boundaries of accuracy? (e.g., "Complexity scores match SonarQube within ±5% for most patterns")

**A deliverable with no documented limitations is either trivial or undertested.** Enterprise clients trust tools that are honest about boundaries more than tools that claim perfection.

### 4. Performance Profiling

**"It works" is not "it performs." Every deliverable must include performance evidence at realistic scale.**

| Deliverable Type | What to Profile |
|-----------------|----------------|
| Code / CLI tool | Wall-clock time, peak memory (RSS), disk I/O, CPU utilization. Profile at 1x, 5x, and 10x expected scale. Report the scaling curve, not just a single number. |
| Website / web app | Lighthouse performance score, First Contentful Paint, Largest Contentful Paint, Total Blocking Time, bundle size breakdown. |
| Data / CSV / spreadsheet | Processing time per 1K rows, memory at peak, output file size. Profile at 10x expected row count. |
| Dashboard / visualization | Initial load time, re-render time on filter change, memory with max dataset loaded. |
| API / MCP server | Response time (p50, p95, p99), requests/second capacity, memory under sustained load. |
| 3D renders / images | Render time per frame, scene complexity (polygon count, texture memory). |
| Video / animation | Encode time, output file size, bitrate. |
| Game / interactive app | Frame rate (min/avg/max), load times, memory usage during longest play session. |
| PDF / document / report | If programmatically generated: generation time, file size. For large reports: profile at 2x page count. For manually authored or single-generation documents: file size only (no performance profiling required). |
| Email (client-facing) | N/A — no performance profiling required for email deliverables. |

**Measurement must be reproducible.** Include the corpus, hardware baseline, and measurement command so the client can re-run it.

### 5. Security Hardening

**Every deliverable touching user input, network, or credentials must be security-reviewed.**

| Concern | Verification |
|---------|-------------|
| Input sanitization | No `eval()`, `exec()`, unsanitized SQL, or shell injection vectors. All user-facing input validated. |
| Dependency audit | Run `pip audit`, `npm audit`, or equivalent. Zero known critical/high vulnerabilities in shipped dependencies. |
| Credential handling | No credentials in code, config files, or git history. All secrets from environment variables. |
| Network exposure | No unintended listening ports. Localhost-only services bound to `127.0.0.1`, not `0.0.0.0`. |
| Data privacy | No PII logged or transmitted without consent. Scrubbed from error messages and stack traces. |
| OWASP Top 10 | For web deliverables: CSP headers, no inline scripts, CSRF protection, secure cookie flags. |

**The Codex pre-delivery gate already runs a security scan.** This section ensures the build agent addresses security during development, not just at the gate.

### 6. Error Recovery and Resume

**Enterprise tools don't lose work when they fail.**

| Deliverable Type | Recovery Requirement |
|-----------------|---------------------|
| Code / CLI tool (read-only analysis) | Long-running operations must checkpoint progress. If the process is killed at 80%, restarting should resume from ~80%, not 0%. Partial results must be preserved, not discarded. |
| Code / CLI tool (mutating operations) | Mutations (refactoring, migrations, file transformations) must be atomic — commit or rollback, never leave the target in a half-modified state. Use git branches, temp files, or transactions. The creative brief defines which recovery strategy applies. |
| Data / CSV / spreadsheet | Failed rows are logged and skipped, not silently dropped. The output includes a manifest of what succeeded and what failed. |
| Dashboard / visualization | Graceful degradation when data source is unavailable. Show last-known-good data with staleness indicator, not a blank screen. |
| API / MCP server | Transient failures (network timeout, rate limit) must retry with backoff. Permanent failures return descriptive errors, not crashes. |
| Website / web app | Forms preserve user input on validation failure. Network errors show retry options, not blank screens. |
| Game / interactive app | Auto-save at meaningful intervals. Crash recovery returns to last checkpoint, not title screen. |
| PDF / document / report | N/A — static deliverables don't have runtime recovery requirements. |
| 3D renders / images | N/A — static deliverables don't have runtime recovery requirements. |
| Video / animation | N/A — static deliverables don't have runtime recovery requirements. |
| Email (client-facing) | N/A — static deliverables don't have runtime recovery requirements. |

**"Zero crashes" on the happy path is necessary but not sufficient.** The QC playthrough/test suite must include at least one forced failure scenario (kill the process mid-operation, feed corrupt input, disconnect network) and verify recovery. For static deliverables marked N/A, this requirement is waived.

## Verification Protocol Reference

**This section defines the proof-of-correctness categories for each deliverable type.** The creative brief's `## Verification Protocol` section draws from these categories. Quality-check and self-review execute the protocol. This reference ensures every domain has a defined proof method so new project types don't fall through the cracks.

Every deliverable type has three proof layers:
1. **Build/Generation Proof** — can the artifact be produced from source?
2. **Automated Verification** — do the machine-checkable properties hold?
3. **Domain-Specific Proof** — does the content satisfy domain correctness requirements?

| Deliverable Type | Build/Generation Proof | Automated Verification | Domain-Specific Proof |
|-----------------|----------------------|----------------------|---------------------|
| **Compiled software** (Tauri, Electron, native) | `cargo build`, `npm run build`, `dotnet build`, etc. Exit code 0. | `cargo test`, `npm test`, `dotnet test`. All pass. Launch binary, verify window/output. | N/A unless domain-embedded (e.g., financial engine — verify calc outputs) |
| **Website / HTML** | N/A (static) or `npm run build` (frameworks) | `agent-browser` screenshot + interaction. Lighthouse >90. All links HTTP 200. | Content accuracy: verify claims, prices, hours against source |
| **Python tool / script** | `pip install -e .` or `pip install -r requirements.txt`. Exit 0. | `pytest` or `python -m unittest`. All pass. Run with sample input, verify output. | N/A unless domain-specific (e.g., scientific tool — verify calculations) |
| **Data / CSV** | Generation script runs without error. Output exists with expected row count. | Schema validation (columns, types, no unexpected nulls). Aggregates match source. | Cross-reference sample rows against source data. Verify enrichment coverage. |
| **PDF / Document / Report** | Generation tool produces PDF without error. Page count matches. | TOC links work. No blank pages. Images render. Text searchable. | Citations exist at source. Statistics match source. Calculations reproduce independently. |
| **Legal document** | Document generates/renders correctly. | Formatting complies with jurisdiction requirements (margins, font, spacing). | For each citation: (1) search CourtListener API or Google Scholar with case name + year, (2) verify case exists and year matches, (3) verify the holding/rule cited supports the claim made. Log: citation text, source searched, found (yes/no), year match (yes/no), holding supports claim (yes/no). 100% of citations must verify. |
| **Engineering spec** | Document/model generates without error. | Units consistent throughout (grep for unit conflicts). Dimensions within tolerance. | For each calculation: (1) extract input values and formula from spec, (2) compute independently (Python/calculator), (3) compare result — must match within stated tolerance or ±0.1% if no tolerance specified. Log: calc ID, inputs, expected, actual, delta, pass/fail. |
| **Research / academic paper** | Document compiles (LaTeX) or generates without error. | Bibliography entries resolve (DOI lookup or URL HTTP 200). Figures/tables referenced in text. | For each cited statistic: (1) fetch the original source URL/DOI, (2) locate the specific number in the source, (3) verify it matches. Log: claim text, source URL, source value, match (yes/no). Flag any claim with only a single source. |
| **Medical / clinical document** | Document generates without error. | Terminology verified against ICD/CPT/SNOMED lookup APIs. Drug names verified against FDA NDC database or WHO INN list. | For each dosage: (1) extract drug, dose, route, frequency, (2) verify against clinical reference (e.g., Lexicomp ranges, FDA label), (3) flag if outside standard range. For each contraindication claim: verify against FDA drug label or clinical guideline. Log: drug, dose, reference range, within range (yes/no). |
| **Financial analysis / model** | Spreadsheet/model opens without circular reference errors. | Formulas produce expected outputs for 3+ known test input sets. Aggregates match detail row sums. | For each market data point: verify against Yahoo Finance API, SEC EDGAR, or stated source. For each ratio: verify formula matches GAAP/IFRS definition (e.g., P/E = price / trailing 12mo EPS, not price / forward EPS unless stated). Log: metric, stated value, verified value, source, match (yes/no). |
| **Game / interactive** | Engine export/build. Exit 0. | Playthrough verification per game QC. All core mechanics respond. | Genre-specific: physics accuracy, scoring math, progression balance per design doc. |
| **API / MCP server** | `pip install` / `npm install`. Server starts without error. | All endpoints respond to valid requests. Error handling for invalid requests. [[test-mcp-server]] protocol. | Response data matches upstream source. Rate limits enforced. Auth works correctly. |
| **Presentation / slides** | PPTX generates without error. LibreOffice converts to PDF. | Per-slide PNG visual inspection. No overlapping shapes. All text readable. | Content claims verified against source data. Charts match underlying data. |
| **Email campaign** | HTML renders in email clients. | Renders across 3+ clients. Links work. Images load. Responsive on mobile. | CAN-SPAM compliance. Unsubscribe works. Claims match source. |
| **3D renders / images** | Render completes without error. Output file valid. | Resolution meets spec. No artifacts, clipping, or z-fighting. | Subject matches brief. Style consistent across set. |
| **Dashboard / data visualization** | `npm run build` or framework build. Exit 0. | Screenshots at 3+ viewports. Filters/interactions work. Lighthouse >80. | Chart values trace to source queries. Aggregates match raw data. |
| **Code / scripts** (standalone tools) | `pip install`/`npm install`. Exit 0. | `pytest`/`npm test`. All pass. Run with `--help` and sample input. | Output matches expected for known inputs. Error handling for bad input. |
| **Video / animation** | Encode completes. Output playable. | Resolution, framerate, duration, codec match spec. No audio sync issues. | Content matches storyboard/brief. Transitions intentional. |

**Computer use is available.** Claude Code can interact with the desktop — launch apps, click UI elements, fill forms, navigate browsers. For functional proofs, prefer direct interaction over CLI workarounds when the proof requires GUI verification. Let Claude choose the best approach for the task.

**Screenshot evidence (MANDATORY for functional proofs involving visual deliverables):** Every functional proof step for a visual deliverable (desktop app, website, dashboard, game, mobile app) must include a screenshot. Use the runtime-appropriate capture tool: `agent-browser screenshot` for web/browser-based deliverables, `screencapture -x` for native macOS apps (when display access is available), or Playwright for WebView-based apps. Save screenshots to `{deliverables_path}/` using the existing QC naming convention: `qc-screenshot-{proof-name}.png`. Create the target directory if it doesn't exist (`mkdir -p`). A functional proof for a visual deliverable without a screenshot is not proof — it's a claim. For CLI-only deliverables (scripts, APIs, data pipelines), captured command output (stdout/stderr) saved to a log file serves as evidence.

**For unlisted deliverable types:** Define a custom protocol in the creative brief using the three-layer structure. The principle is: if a human expert would verify something before signing off, the protocol must include a machine-executable approximation of that verification.

## How to Use

**Self-review:** Before closing any build ticket, check the deliverable against these standards. Ask: "Would a Fortune 500 client pay premium rates for this?" If the answer is anything other than an immediate yes, it's not done.

**Quality check:** Evaluate against the brief, the per-type standards, the Enterprise Quality Gate, AND the Verification Protocol. A deliverable that meets every brief requirement but looks amateur is a FAIL. A deliverable that looks polished but hasn't been validated against ground truth is also a FAIL. A deliverable that passes all visual and functional checks but whose build or test suite was never executed is also a FAIL. The brief defines scope — per-type standards define craft — the enterprise gate defines trust — the verification protocol defines proof.

**Creative brief:** The brief focuses on client-specific choices. These standards are assumed and never lowered. The brief can only raise the bar higher.

**Iteration is expected:** If meeting these standards requires multiple build-review cycles, that's normal. Enterprise quality doesn't come from a single pass. Break the work into phases, iterate, and don't ship until it's genuinely excellent. Time is a variable. Quality is the constraint.

## See Also

- [[self-review]]
- [[quality-check]]
- [[creative-brief]]
- [[build-mcp-server]]
- [[SCHEMA]]
