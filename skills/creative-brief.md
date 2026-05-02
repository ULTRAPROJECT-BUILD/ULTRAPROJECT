---
type: skill
name: creative-brief
description: Creates a detailed project or ticket brief before delivery work — defines the quality bar, deliverable contract, references, and specific acceptance criteria
inputs:
  - client (optional — client slug for client-scoped work)
  - project (required — project slug)
  - ticket_id (optional — the ticket creating this brief; required only for ticket-scoped briefs)
  - phase_number (optional — required for phase-scoped briefs)
  - phase_title (optional — short phase name for phase-scoped briefs)
  - parent_brief_path (optional — governing project brief when writing a phase-scoped addendum)
  - covered_waves (optional — list of wave names when a phase-scoped brief only governs specific capability waves)
  - task_description (required — what's being built)
  - brief_scope (optional — project, phase, or ticket; default: project)
  - applies_to_tickets (optional — execution/review ticket IDs that should consume this brief)
  - client_requirements (optional — parsed from clarification ticket or project notes if not provided)
  - research_context_path (optional — latest research-context snapshot to use for current references, tools, vendors, genre benchmarks, and deprecated-pattern warnings)
---

# Creative Brief

You are creating the brief before real work begins. This is the most important step in producing professional output. Do NOT skip this. The brief becomes the spec that executors, self-review, and quality-check work from — without it, output will be generic and mediocre.

**Default mode:** create a **project-level brief**

**Scope model:**
- `project` — the master contract for the whole project. This is the default.
- `phase` — a short addendum for a single phase when that phase has a materially different proof contract, evaluator lens, evidence package, or anti-pattern set. A phase brief supplements the project brief; it does not replace it.
- For `execution_model: capability-waves`, a phase brief may either govern the whole anchor phase or only specific waves. When it is wave-limited, record that explicitly in `covered_waves` frontmatter.
- `ticket` — the narrowest exception, used only when one ticket genuinely needs a materially different local contract.

## Process

### Step 1: Understand the Context

1. Read the project file first, then the current ticket if `ticket_id` is provided.
   - If `brief_scope: phase`, also read the governing project brief (`parent_brief_path` when provided, otherwise resolve the latest project-scoped brief first). A phase brief is an addendum, not a fresh independent worldview.
   - **Master-brief rule:** if `brief_scope: phase` or `brief_scope: ticket` and no project-scoped brief exists yet, STOP and report that the master project brief is missing. Do NOT author a phase/ticket brief as if it were the root contract.
   - Read the project plan's `## Goal Contract` and `## Assumption Register` first when they exist. The brief should consume those contracts, not reinvent them.
   - If a `research-context.md` snapshot exists, read it before researching genre excellence standards. Use it as the currentness baseline for recent launches, current tool/library versions, deprecated patterns, new capabilities since cutoff, and current best practices. Treat `total_websearch`, `total_webfetch`, and the per-category count maps as cost-and-coverage context only. Do not copy the whole snapshot into the brief. Pull only cited claims that affect references, quality bar, recommended tooling, anti-patterns, media strategy, proof strategy, or Executability Audit. If the snapshot has `low_confidence: true`, cite those items only as assumptions or risks unless independently verified in the brief.
2. If `client` is provided:
   - Read the client's `config.md` for industry, domain, and notes.
   - Read all clarification/discovery tickets and incoming snapshots for details about what they want.
3. If `client` is NOT provided:
   - Read the relevant project notes, prior tickets, and any platform snapshots or decisions that define the goal.
   - Identify the audience, channel, and business objective from the project itself.
4. Before reading any playbooks, write a one-paragraph **first-principles hypothesis** of what excellent output for this project should look like based on the current requirements, audience, channel, and genre benchmarks. This prevents archived work from becoming the default answer.
5. Read any relevant playbooks via [[match-playbooks]] for what worked on similar projects. Use the project plan's `## Playbook Usage Contract` if it exists. If no contract exists, default to the safest mode: `pattern_only`.
   - `pattern_only` — use for lessons, risks, anti-patterns, and process shape. Do NOT inherit architecture proof, scale proof, product shape, or creative direction.
   - `component_reuse` — bounded modules/checklists/scripts may be reused, but the brief still needs fresh project-specific reasoning.
   - `template_allowed` — only for low-novelty repeatable work. Even here, client-specific claims and scale claims must be re-proven.
   - Quality classifications still matter:
     - **Full reference** — strongest prior art, but still bounded by the reuse mode.
     - **Structure only** — sequencing/capability sourcing only. Do NOT copy output quality or worldview.
     - **Cautionary** — anti-patterns only.
6. Identify:
   - **Industry/niche** — what business are they in?
   - **Audience** — who are their customers?
   - **Competitors** — who are they competing with?
   - **Tone** — professional? playful? luxury? rugged? minimal?
   - **Existing brand** — do they have colors, logos, fonts, or a brand voice already?

### Step 2: Research Genre Excellence Standards

**Before writing a single line of the brief, understand what BEST-OF-THE-BEST looks like for this exact project type.** Start from research-context references when present, then use only additional scoped WebSearch needed for visual, genre, or evaluator examples not already covered. The system must know what it's competing against without duplicating currentness research that already passed through `research-context.md`.

**Phase-brief exception:** when `brief_scope: phase`, inherit the project-level genre benchmarks by default. Do NOT repeat a full benchmark section unless this phase introduces a meaningfully different evaluator lens (for example: adversarial clean-room review, compliance review, artifact-polish review). Phase briefs should usually add only the phase-specific benchmark delta.

**Genre-specific excellence benchmarks (use as starting points, then research deeper):**

| Project Type | Excellence Benchmark | What Makes It Great |
|-------------|---------------------|---------------------|
| SaaS dashboard | Stripe Dashboard, Linear, Grafana, Datadog | Information density without clutter, semantic color, responsive data viz, keyboard shortcuts |
| Landing page | Stripe.com, Vercel, Linear, Notion | Bold typography, scroll animations, clear value prop in 5 seconds, social proof, conversion-optimized |
| FPS game | DOOM (2016), Half-Life 2, Halo, Valorant | Weapon feel (recoil, screen shake, audio layering), AI that uses cover, lighting that creates tension, 60fps |
| Portfolio website | Apple.com, Pentagram, Fantasy.co | Immaculate spacing, hero imagery, case study storytelling, craft in every pixel |
| Data report/analysis | McKinsey reports, The Economist charts, FiveThirtyEight | Clear narrative arc, evidence-driven, beautiful data viz, executive summary that stands alone |
| Communication campaign | Best-in-class lifecycle and launch messaging examples | Scannable, single CTA per message, mobile-first, personality in the copy |
| Presentation deck | Apple keynotes, Sequoia pitch deck template, TED talks | One idea per slide, big visuals, minimal text, narrative flow |
| E-commerce site | Shopify Dawn theme, Allbirds, Warby Parker | Product photography, frictionless checkout, trust signals, speed |
| Mobile app | Arc Browser, Things 3, Spotify | Gesture-driven, delightful micro-interactions, zero unnecessary screens |
| Brand identity | Pentagram case studies, Collins, Wolff Olins | System thinking (not just a logo), applications across touchpoints, guidelines that enable |
| Video/animation | Apple product videos, Stripe Sessions, Remotion showcases | Pacing, typography in motion, sound design, story in 30 seconds |
| RPG/strategy game | Baldur's Gate 3, Civilization, Hades | Deep systems, meaningful choices, polish in every interaction, 100+ hours of content feeling intentional |
| Nonprofit/NGO site | charity: water, Khan Academy, Doctors Without Borders | Impact storytelling, donation UX, transparency, emotional resonance |
| Data pipeline/CSV | FiveThirtyEight datasets, Kaggle top datasets, US Census data products | Clean schemas, documented methodology, validation reports, coverage metrics |
| 3D renders/visuals | Behance top 3D work, ArtStation trending, Pixar shorts | Lighting, composition, material quality, storytelling through image |
| Research report/proposal | McKinsey Global Institute, Bain briefs, a16z research | Narrative arc, evidence density, actionable recommendations, executive summary |
| API/MCP server | Stripe API, Twilio API, GitHub API | Clear docs, consistent error handling, sensible defaults, comprehensive tooling |
| Blog/content | Stratechery, Paul Graham essays, Intercom blog | Deep analysis, original thinking, scannable structure, clear voice |
| Local business site | Best-in-class Squarespace/Wix showcase sites | Location prominent, mobile-first, click-to-call, Google Maps, reviews integration |

**Process:**
1. Identify the project's genre from the table above (or the closest match).
2. **WebSearch for 3-5 real examples** of the best work in that genre. Not hypothetical — actual URLs the agent visits and analyzes.
3. For each reference, document specifically what makes it excellent — layout, interaction design, typography, content strategy, technical execution, emotional impact.
4. Set the quality bar: "Our deliverable must compete with these. If it wouldn't look at home next to {reference}, it's not done."
5. Save the references and analysis in the brief. These become the acceptance criteria for self-review and QC.

**The brief should explicitly state: "This project targets {genre} excellence. Reference benchmarks: {list}. The deliverable is not complete until it would be indistinguishable from work produced by a top-tier agency."**

### Step 3: Define the Creative Direction

Write a project brief that covers the dimensions relevant to the work:

**Mission Alignment Map (MANDATORY — must appear before Deliverable Contract):**

Before defining any acceptance criteria, extract every non-negotiable goal, workstream, or stated requirement from the original client/admin request. For each one, map it to specific, measurable acceptance criteria that prove it is satisfied. Use this format:

| Mission Goal / Workstream | Acceptance Criteria | How Verified | Scale / Scope |
|--------------------------|--------------------|--------------|---------------|
| {exact goal from original request} | {specific, measurable criterion} | {test, measurement, or evidence method} | {what scale this criterion proves, e.g. "3,578-file Chromium shard" vs "full 490K-file Chromium repo" vs "154K-entity CPython"} |

Rules:
- Every mission goal MUST have at least one acceptance criterion. If a goal has zero criteria, the brief is incomplete — add criteria or escalate to admin with a descope request.
- Acceptance criteria must match the ambition of the stated goal. If the admin says "enterprise-scale" and the criterion accepts a 5K LOC proof on the easiest target, that's a mismatch — flag it with `[PARTIAL-COVERAGE]` and explain what full coverage would require and why it's not achievable.
- When the original request uses scale language (`millions of lines`, `enterprise-scale`, `Chromium-class`, `brutal real-world`, `at scale`), the acceptance criteria must prove at a scale consistent with that language. If the criterion proves at a materially smaller scale (e.g., a shard instead of the full repo, a toy target instead of a production-sized codebase), it must be flagged `[PARTIAL-COVERAGE]` with justification explaining why full-scale proof is infeasible and what the gap means. Do NOT silently accept shard-scale criteria as satisfying full-scale ambition language.
- If a goal is genuinely out of scope for this project, flag it as `[DESCOPED]` in the map with the reason and state: "Admin approval required before proceeding." Do NOT silently omit goals or write soft criteria that technically pass but don't satisfy the intent. The Mission Completion Gate at delivery will classify descoped goals as DESCOPED-APPROVED (admin approved) or DESCOPED-UNAPPROVED (admin never approved — blocks delivery).
- The Mission Alignment Map is the primary input for the Mission Completion Gate at delivery time. Every goal listed here will be verified against actual deliverables before the project ships.

**Proof Strategy (MANDATORY — must appear after Mission Alignment Map):**

The brief must explicitly state what kind of proof this work requires. Build on the Goal Contract and Assumption Register rather than inventing a disconnected proof story.

Include these required fields:
- `Rigor tier`
- `Evaluator lens`
- `Proof posture`
- `Primary evidence modes`
- `False-pass risks`
- `Adversarial / skeptical checks`
- `Phase-level adversarial probe pack` (when this brief governs a risky feature-heavy implementation phase)
- `Rehearsal lenses`
- `Drift sentinels`
- `Supplement trigger`
- `Gate impact`

Rules:
- `lightweight` projects may keep this short, but it still must exist
- `standard` projects should make clear why the normal project brief is sufficient or why a phase/ticket supplement exists
- `frontier` or trust-sensitive work must state a real skeptical/adversarial angle — not "N/A" hand-waving
- phase briefs should usually describe the **proof delta** for that phase rather than restating the entire project brief worldview
- if a **phase-scoped brief** governs a risky feature-heavy implementation phase (auth/security, native runtime, governed writes, ingestion/parsing, retrieval/memory/sync, integrations/tool access, live watch/media/artifacts), add a dedicated `## Phase-Level Adversarial Probe Pack` section. That section should define:
  - `Trigger rationale`
  - `Target risk families`
  - `Bad-input / degraded-state probes`
  - `Pass threshold` (default: zero blockers, zero majors)
  - `Client-safe exclusions` (what the probe deliberately does NOT attack yet)
  - `Gate impact`
  The section should also set frontmatter when possible:
  - `phase_adversarial_probe_required: true`
  - `adversarial_probe_risk_families: [family-a, family-b]`
  This is the contract the phase-level adversarial probe planner consumes. Review/polish/delivery phases normally omit it.

**Deliverable Contract:**
- Deliverable formats — exactly what files/artifacts the client should receive
- Structure — required sections, sequence, or packaging expectations
- Acceptance criteria — specific checks for "done well"
- Proof/evidence standard — what facts, citations, screenshots, calculations, or validations must support the work
- Failure modes to avoid — what would make this feel generic, untrustworthy, or incomplete
- **Data formatting overrides (only when the client needs something DIFFERENT from [[deliverable-standards]] defaults):** e.g., European number format `1.234.567,00`, specific date format, custom sort order. Baseline formatting (currency with `$`, readable headers, leading zeros) is handled automatically by deliverable-standards and does NOT need to be specified here.
- **Data schema definition (mandatory when the project has 10+ instances of the same type):** When a deliverable involves many instances of a single type (weapons, products, pages, entities, campaigns, widgets), the brief must define a data schema: field names, types, constraints, and the behavior contract (what each field controls). This enables data-driven architecture where content scales without proportional code growth. Adding instance #43 should mean adding a dictionary entry, not writing a new script. (Learned from 2026-03-18-data-driven-architecture-scales-content-not-code, 2026-03-18)
- **Domain-plugin architecture (mandatory when generalizing a single-domain system):** When a project involves making a domain-locked system work across multiple domains, the brief must define: (a) domain definition files with task types, KPIs, scoring weights, classification keywords, and skill mappings; (b) which parts of the engine are already domain-agnostic and should NOT be rewritten; (c) negative keywords for hard domain boundaries (what each domain excludes, not just what it matches). Build real domains with genuine metrics, not stubs. The hardest part is recognizing what to keep unchanged. (Learned from forge-agents/2026-03-19-domain-plugin-architecture-pattern, 2026-03-19)
- **Directory structure specification (mandatory for multi-file deliverables):** When the deliverable will consist of multiple interdependent files (engine projects, multi-page apps, services with separate modules), the brief must include the expected directory structure. This allows the project plan to choose the correct ticket strategy: single deep ticket for single-file deliverables, multi-ticket phased build for multi-file projects with 5+ interdependent files. (Learned from 2026-03-18-multi-ticket-phased-build-works-for-engine-projects, 2026-03-18)
- **Target runtime and user acceptance test (mandatory)** — for EVERY deliverable, specify:
  1. What the user will use to open/run it (browser, Godot, Python, Excel, native app, etc.)
  2. The exact steps a user would take to verify it works (e.g., "open in browser, click Start Match, verify gameplay loads without errors")
  3. How QC should simulate this — the automated test command or procedure

  Examples:
  - Website: "Open index.html in browser → `agent-browser` full-page screenshot + interaction smoke test via snapshot -i and ref clicks"
  - Godot game: "Export to HTML5 via `godot --headless --export-release Web` → `agent-browser --allow-file-access open` → screenshot → snapshot -i → click Start ref → verify no errors"
  - Python tool: "Run `python3 tool.py --test` → verify exit code 0 and expected output"
  - PPTX slides: "Convert to per-slide PNGs via LibreOffice headless → visually inspect each slide for overlapping shapes, text overflow, broken layouts, and contrast issues"
  - PDF report: "Open with Preview/browser → verify page count, section headers present, no blank pages"
  - API/MCP: "Run test-mcp-server → verify all tools respond"
  - Executable: "Launch → verify main window appears → verify primary function works"

  If a deliverable CANNOT be tested automatically, the brief must say so explicitly and mandate a human-review ticket. "We'll check if the files exist" is never an acceptable test plan.
- **Verification Protocol (mandatory for code/software/tool deliverables; recommended for all others)** — a concrete, executable proof-of-correctness specification. The Runtime Acceptance Test above defines what the USER does to verify. The Verification Protocol defines what the AGENT does to PROVE it works before the user ever sees it. This is not a description of intent ("verify it compiles") — it is a runnable command sequence with expected outputs.

  For **code/software/tool deliverables** (compiled apps, scripts, APIs, games, dashboards), the protocol MUST include:
  1. **Build verification** — the exact commands to build/compile/generate the deliverable from source, with expected exit codes.
  2. **Test suite execution** — the exact commands to run the project's test suite, with expected pass counts or exit codes.
  3. **Functional proof** — at least one command or sequence demonstrating the deliverable's primary function works end-to-end.
  4. **Regression anchor** — for multi-phase projects, which subset of the protocol must pass at EVERY phase gate.

  For **static deliverables** (HTML, PDF, presentations, images, video) where no build step or test suite exists, the Runtime Acceptance Test (above) serves as the verification protocol. No separate protocol section is required — note "Verification Protocol: covered by Runtime Acceptance Test" in the brief.

  For **knowledge deliverables** (legal briefs, research reports, engineering specs, medical docs, financial analyses), the protocol SHOULD include a **Domain-Specific Verification** section with concrete verification methods. If the domain lacks machine-checkable verification (e.g., no citation API available), the brief must mandate a human-verification ticket and document why automated verification is infeasible.

  The protocol is domain-aware. Use the Verification Protocol Reference in [[deliverable-standards]] to determine the appropriate proof method. If the deliverable type is not covered, define a custom protocol and document why.

  Examples:
  - Tauri desktop app: `npm install` (exit 0), `cargo build --release` (exit 0), `cargo test` (all pass), `npm test` (all pass), launch binary and verify window opens
  - Python data pipeline: `pip install -e .` (exit 0), `pytest tests/ -v` (all pass), `python pipeline.py --input sample.csv --output /tmp/out.csv` (exit 0, output has expected row count)
  - Legal brief: verify every case citation against CourtListener or Google Scholar (citation exists, year matches, holding supports claim)
  - Engineering spec: reproduce every calculation independently (input -> formula -> output matches within tolerance)
  - Research report: verify every cited statistic against its original source URL
  - Marketing website: `agent-browser` open + screenshot (renders), Lighthouse >90, all links HTTP 200

  If a code/software deliverable CANNOT have an executable verification protocol, the brief must explicitly state why and mandate a human-verification ticket.

  **Legacy briefs (created before 2026-03-23):** Existing creative briefs written before the Verification Protocol requirement do not retroactively require a protocol section. QC for legacy briefs uses the Runtime Acceptance Test section as the verification method. New briefs created on or after 2026-03-23 MUST include the protocol for code/software deliverables.
- **Scope matrix** (mandatory when the client's request exceeds what can be built in one pass) — list every requested system/feature with an explicit IN or OUT decision and rationale. This transforms an unfinishable project into a focused, achievable deliverable. Every IN-scope item must be fully implemented; every OUT-scope item must be cleanly excluded. The quality bar criteria should map exactly to IN-scope features. (Learned from 2026-03-18-scope-matrix-prevents-gdd-overwhelm, 2026-03-18)
- **Data enrichment feasibility (mandatory for data/CSV deliverables):** When the deliverable involves data enrichment (e.g., adding website URLs, phone numbers, contacts to a dataset), validate the actual coverage of each data source BEFORE setting acceptance criteria. Do not assume an API provides a field — test it. Set realistic per-column coverage targets based on verified source capabilities. For nonprofit data specifically: IRS BMF provides identity and financials only; ProPublica provides filing data only (no URLs, phones, or contacts); IRS Form 990 XML e-filings provide URLs (~15%), phones (~27%), and contacts (~27%) but only for the ~30% of nonprofits that e-file. GuideStar/Candid has the best coverage but requires a paid subscription. A brief that promises "website URLs for all orgs" from free sources is setting up a delivery failure. (Learned from 2026-03-18-irs-990-xml-enrichment-strategy and 2026-03-18-propublica-no-website-urls, 2026-03-18)
- **Playbook usage contract (mandatory when prior art is in scope):** Add a `## Playbook Usage Contract` section that records the reuse mode from the plan (`pattern_only`, `component_reuse`, or `template_allowed`), which playbooks matched, what can be imported safely, and what is forbidden from inheritance.
- **Why this cannot just be the playbook (mandatory for frontier/high-novelty work):** Add a `## Why This Cannot Just Be The Playbook` section that states what is materially different here, what the old project does not prove, and what must be originated or re-proven from scratch.

**Presentation Direction (when applicable):**
- **Consult the UI/UX Pro Max skill** (`vault/archive/skills/ui-ux-pro-max/`) for industry-specific design intelligence. Match the project's domain against the product types database (`data/products.csv`) to get recommended styles, color psychology, anti-patterns, and accessibility requirements. For example, a Senior Care app should use the "Accessible & Ethical + Soft UI Evolution" style with "Calm Blue + Warm neutrals + Large text" — not the same palette as a fintech dashboard. The skill also has React Native stack guidelines (`data/stacks/react-native.csv` — the only stack archived locally) and UX guidelines (`data/ux-guidelines.csv`). **Important: agents should read the CSV files directly, not run the Python scripts** (scripts have known bugs). Use these to inform the brief's design decisions rather than defaulting to generic choices. Note: if the client has provided their own brand guidelines, those take precedence — use the skill for accessibility validation and anti-pattern checking, not to override the client's established brand.
- Color palette — primary, secondary, accent colors with hex codes. Derive from the UI/UX Pro Max product-type color recommendations, client preferences, or reference sites. Don't default to generic blue/green.
- Typography — specific font pairing (heading + body). Consult the typography database (`data/typography.csv`) for mood-matched pairings. Recommend Google Fonts for web projects.
- Imagery style — photography vs illustration vs 3D. High contrast vs soft. Warm vs cool.
- **Media specification (mandatory for deliverables with visual/audio/video elements)** — list every media asset needed, where it goes, and what it should show. Without this, build agents produce text-only output that looks like a template. For each asset, specify:
  - **Location** — which section/component it belongs to (e.g., "hero background", "slide 3", "game splash screen", "report cover")
  - **Subject** — what the asset shows (e.g., "team collaborating around a laptop", "10s product demo loop", "ambient background music")
  - **Type** — image, video, animation, audio, data visualization, 3D render
  - **Style** — photography, illustration, screen recording, motion graphics, generative, gradient/pattern
  - **Dimensions/format** — e.g., "1920x800 hero banner", "16:9 MP4 15s", "9:16 vertical reel", "WAV 30s"
  - **Source strategy** — how to get it:
    - Stock photo: "Source from Unsplash/Pexels: search '{keywords}'" (when stock photo MCP is available)
    - AI-generated image: "Generate via image MCP: '{prompt}'" (when image generation MCP is available)
    - Video: "Create via Remotion: '{scene description}'" (when build-remotion-video skill is available)
    - Audio: "Source via source-audio skill: '{description}'" (when source-audio skill is available)
    - SVG/CSS: "Create as CSS gradient" or "Generate as inline SVG pattern" (always available, no MCP needed)
    - Data viz: "Generate as SVG chart from {data source}" (always available)
    - Client-provided: "Use client's existing {asset}" (when client has assets)
  - **Fallback** — if the preferred source isn't available, what to use instead (e.g., "CSS gradient overlay", "static image instead of video", "SVG animation instead of video")

  Include this section when the deliverable requires non-text media assets to meet the quality bar — websites, brand packages, presentations, games, video content. Omit it for pure data deliverables (CSVs, datasets), developer tools, or text-only reports where media wouldn't add value.
- Layout philosophy — dense vs spacious. Grid-based vs organic. Card-heavy vs editorial.
- Tone and messaging — benefit-driven, emotional, factual, concise, detailed, executive, etc.

**Quality Bar:**
- Define what "done well" looks like with specific, measurable criteria.
- Example: "The hero section should feel like a premium brand — not a template. Full-bleed imagery, large confident typography, clear CTA above the fold."
- Example: "The 3D renders should look photorealistic at first glance, not obviously low-poly or toy-like."
- Example: "The stock research report must name specific tickers, show evidence for each thesis, separate technical vs fundamental reasoning, and surface risks clearly enough that a skeptical reader can audit the logic."
- Example: "The outreach sequence must speak to the target segment's actual pain points, use a concrete CTA, and avoid sounding like a bulk AI spam draft."

**Tooling & Plugins (inventory only — do not install here):**
- Before specifying the build approach, check what tools are available and recommend them:
  - In Claude Code: `/plugin list` (or from shell: `claude plugins list`) to see installed plugins
  - `npx skills search "{relevant keywords}"` for marketplace skills
  - Check `.mcp.json` and `vault/archive/_index.md` for existing MCPs
- Note recommended tools in the brief (e.g., "Use the `frontend-design` plugin for HTML/CSS work"). Actual installation happens during the capability-sourcing ticket, not here.

**Robustness & Stress Testing (mandatory for tool/software/API deliverables):**
When the deliverable is a tool, CLI, API, MCP server, data pipeline, agent, or any software that processes external input, the brief MUST include:

1. **Real-world test corpus** — at least one project or dataset that resembles the target use case. Fixture repos with 500 LOC don't prove a tool works on 100K LOC production codebases. Specify:
   - A public open-source repo/dataset of realistic size and messiness, OR a client-provided/internal corpus when no public analog is representative
   - Why it's representative (e.g., "has circular imports, mixed Python 2/3, no existing tests")
   - Expected behavior on that corpus (e.g., "indexes in under 60s, identifies 10+ hotspots")

2. **Stress test criteria** — what's the ugliest, most adversarial input this needs to handle?
   - Edge cases: empty input, malformed data, enormous files, deeply nested structures, circular references
   - Scale: what's the maximum input size? Define a concrete target (e.g., "must handle repos up to 200K LOC")
   - Concurrency: if applicable, how many simultaneous operations?

3. **Failure mode specification** — what should happen when the tool hits something it can't handle?
   - **Read-only/reporting tools:** graceful degradation (skip the problematic file, log a warning, continue). Partial results should be preserved — if 95 of 100 files process correctly, save those 95
   - **Mutating tools (refactorers, migration scripts, anything that writes back):** atomic abort + rollback is acceptable and often safer than partial writes. A partially mutated codebase that doesn't build is worse than no mutation at all
   - Clear error messages that tell the user what went wrong and what to do — NOT silent corruption or crashes

4. **Confidence/quality signals** — when the tool produces output, how does the user know if it's trustworthy?
   - Confidence scores on automated decisions (e.g., "this refactoring has 98% test coverage" vs "3 tests missing")
   - Metrics that quantify output quality (coverage %, accuracy, precision/recall)
   - Clear distinction between high-confidence automated results and low-confidence suggestions that need human review

QC must verify the tool against ALL stress test criteria, not just the happy-path fixture. A tool that gets Grade A on a 500 LOC fixture but crashes on a 50K LOC real project is a FAIL. (Learned from 2026-03-21: Refactor Engine passed all QC gates on fixture repos but real-world enterprise usage still requires significant manual effort because stress testing criteria were too narrow.)

**Technical Requirements:**
- Responsive breakpoints
- Performance targets (page load time, image sizes)
- Accessibility (contrast ratios, alt text, keyboard navigation)
- Browser support
- For non-visual work: tooling assumptions, export formats, reproducibility requirements, validation steps, and any required handoff notes
- **CDN dependencies (mandatory when applicable):** When the deliverable depends on external CDN libraries (Three.js, D3, React, etc.), specify the exact verified URL — not a vague version reference like "pin r128 stable." The brief must contain URLs that have been verified to return HTTP 200 (e.g., `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js`). Build agents hallucinate library version numbers; an invalid CDN URL produces a deliverable that shows a blank page. (Learned from 2026-03-18-qc-pipeline-catches-cdn-version-bugs, 2026-03-18)

**Local/Physical Business Requirements:**
- If the client is a local/physical business, include a dedicated location section (not just footer) with: embedded map, address with directions link, hours, parking/transit tips, phone number. (Learned from 2026-03-17-location-section-standard-requirement, 2026-03-17)

### Step 3b: Stitch Design Screens (for Stitch-governed UI projects)

**Trigger:** The project produces a visual UI and the governing ticket/plan requires `design_mode: stitch_required`.

**Hard rule:** Stitch is mandatory only when the design contract is `stitch_required`. Use that mode for high-ambiguity/high-drift work such as existing public-surface redesigns, rejected visual work, and complex multi-screen UI. Do not silently downgrade to prose-only visual specs when Stitch should be available.

1. **Create a Stitch project:** Use `mcp__stitch__create_project` with the project name and a description summarizing the creative direction from Step 3.

2. **Generate screens for each major UI state:** Use `mcp__stitch__generate_screen_from_text` for each distinct screen/state the user will see. Name each screen with the pattern `{ComponentName}-{state}`:
   - Examples: `Sidebar-connected`, `ConnectionDialog-empty`, `ConnectionDialog-filled`, `QueryEditor-results`, `ERDViewer-loaded`, `AdminPanel-sessions`, `ErrorState-networkFailure`
   - Cover: the primary view, key secondary views, empty states, error states, loading states

3. **Save screen references in the brief:** Add a "Visual Targets" section to the brief listing each Stitch screen ID and name:
   ```markdown
   ## Visual Targets (Stitch)

   | Screen Name | Stitch ID | State | QC Comparison |
   |------------|-----------|-------|---------------|
   | Sidebar-connected | {id} | Main sidebar with active connection | QC screenshots built app sidebar with active connection and compares |
   | QueryEditor-results | {id} | Editor with query results visible | QC screenshots editor after running a query and compares |
   ```

4. **Define how visual targets feed QC:** For each screen, describe the exact application state QC should capture for comparison. This prevents ambiguity about "what screenshot to take."

5. **Blocked, not degraded:** If Stitch MCP is unavailable (tools not loaded, API error, rate limited):
   - Stop and mark the task **blocked**.
   - Record the exact Stitch failure in the work log.
   - Source/fix the capability before proceeding.
   - Do NOT substitute a prose-only Visual Specification when the design contract is `stitch_required` unless an explicit admin override says the project is legacy-exempt from Stitch.

### Step 3c: Visual Quality Bar, Route Family, Narrative Structure, and Page Contracts (for UI projects)

For user-facing UI/frontend work, the brief must define not just *what exists* but *why the surface feels right*. Stitch is one possible source of truth, not the only acceptable concept mechanism.

Design-mode expectations:
- `stitch_required`: use Step 3b plus the sections below. Stitch is the visual source of truth.
- `concept_required`: the sections below are still mandatory, but the source of truth can be the brief/references/concept package rather than Stitch.
- `implementation_only`: reference the already-approved source of truth explicitly and keep the brief focused on faithful execution rather than new concept invention.

1. **Visual Quality Bar (mandatory for all user-facing UI):** Add a section named `## Visual Quality Bar` that makes the taste bar explicit:
   - Define the intended visual direction in concrete terms (e.g. editorial, cinematic, productized, utilitarian, premium consumer, operational dashboard).
   - Name at least 3 failure modes to avoid.
   - Forbid generic fallback patterns when relevant: card soup, weak hierarchy, too many boxed sections, interchangeable SaaS layout, shallow hero copy, visually unprioritized CTAs.
   - State what should feel immediately true within 2 seconds of loading the page.

2. **Narrative Structure (mandatory for public-facing surfaces):** If the surface is a landing page, homepage, pricing page, marketing site, or other public-facing first-impression page, add a `## Narrative Structure` section that defines the persuasion sequence.
   - Example structure:
     1. Sharp promise / hero
     2. Trust / proof
     3. How it works
     4. Strongest use cases
     5. Why this beats generic alternatives
     6. Pricing / CTA
   - The structure should describe the job of each section, not just list section names.

3. **Composition Anchors (mandatory for public-facing surfaces and route-family-governed operator surfaces):** Add a `## Composition Anchors` section with 3-7 short bullets naming the non-negotiable structural ideas that must survive implementation and be visible in runtime screenshots.
   - Examples:
     - `Two-column hero with the product promise left and a live product module right`
     - `Asymmetrical above-the-fold balance rather than a centered SaaS blob`
     - `Inline proof strip immediately after hero, not buried below feature cards`
     - `Primary list-detail workbench with one dominant review pane and one supporting context rail`
     - `Dense operator shell with calm hierarchy, not a pile of equally weighted cards`
   - These are not mood words. They are concrete visual anchors that QC can verify or fail.

4. **Replace vs Preserve (mandatory for existing-surface redesigns):** If the project is redesigning an already-existing page or screen, add a `## Replace vs Preserve` table:
   ```markdown
   ## Replace vs Preserve

   | Existing Surface Element | Keep / Replace | Why |
   |--------------------------|----------------|-----|
   | Signup wiring | Keep | Functional plumbing is already correct |
   | Current hero layout | Replace | Prevent layout inertia from dragging the redesign back to the old composition |
   ```
   - The default is not "preserve what exists." If something is not explicitly preserved, it is fair game to replace.

5. **Greenfield Concept Pass (mandatory for existing-surface redesigns):** The brief must explicitly state that the design direction was defined as if the current implementation did not exist, and only then mapped back into the real codebase.
   - This is the anti-inertia rule. Existing codebases tend to drag redesigns back toward the old layout. The brief must break that gravitational pull on purpose.

6. **Route Family (mandatory for top-level/internal operator-console surfaces):** If the surface is a primary in-product destination such as Pending Review, Handoff, Memory Browser, Trust Ledger, Audit Timeline, Live Watch, Agent Console, Retrieval / Context, Knowledge Graph, Settings, or another top-level route where product-family consistency matters, add a `## Route Family` section:
   ```markdown
   ## Route Family

   - Family name: `Operator Workbench`
   - Reuse from: `Feedback`, `Approvals`, `Handoff` (or approved Stitch screens)
   - Shared invariants:
     - One dominant work area, not multiple equal-weight panels
     - Supporting context rail is subordinate, not a second homepage
     - The route-level page should not re-introduce a second hero/title block if the shell already owns page identity
     - Avoid card soup, filler metric rails, and generic SaaS split views
   - Allowed deviations:
     - Additional evidence table for review-heavy routes
     - Secondary filter bar when the corpus is genuinely large
   ```
   - The goal is not visual sameness. The goal is same-product-family parity.
   - This section should name which existing routes/screens are the composition relatives, what structural DNA must carry over, and what anti-patterns would make the page feel like a different product.

7. **Page Contracts (mandatory for top-level nav surfaces):** If the UI includes Account, Settings, Billing, Dashboard, Admin, Profile, or similar top-level navigational pages, add a `## Page Contracts` table:
   ```markdown
   ## Page Contracts

   | Page | User Job | Required Sections | Dangerous Actions Placement | States |
   |------|----------|-------------------|-----------------------------|--------|
   | Account | Manage profile, billing, privacy | Profile, billing summary, privacy/data controls, danger zone | Nested in danger zone only | default, empty, loading, error |
   ```
   - A top-level nav destination must not collapse to a single destructive action or one narrow sub-feature unless the brief explicitly says that is the intended product behavior.
   - Destructive actions belong in a clearly labeled danger zone within a broader surface.

### Step 4: Write the Brief

Save the brief to one of these paths:

- **Project-scoped default**
  - Client-scoped: `vault/clients/{client}/snapshots/{project}/{now}-creative-brief-{project}.md`
  - Platform/internal: `vault/snapshots/{project}/{now}-creative-brief-{project}.md`
- **Phase-scoped addendum** (when a phase has a materially distinct proof/review contract)
  - Client-scoped: `vault/clients/{client}/snapshots/{project}/{now}-creative-brief-phase{phase_number}-{project}.md`
  - Platform/internal: `vault/snapshots/{project}/{now}-creative-brief-phase{phase_number}-{project}.md`
- **Ticket-scoped exception** (only when one ticket needs a materially different brief than the rest of the project)
  - Client-scoped: `vault/clients/{client}/snapshots/{project}/{now}-creative-brief-{ticket_id}-{task-slug}.md`
  - Platform/internal: `vault/snapshots/{project}/{now}-creative-brief-{ticket_id}-{task-slug}.md`

```markdown
---
type: snapshot
title: "Creative Brief — {task_description}"
project: "{project}"
brief_scope: "{project|phase|ticket}"
phase: {phase_number or ''}  # omit unless phase-scoped
phase_title: "{phase_title or ''}"  # omit unless phase-scoped
covered_waves: {covered_waves or []}  # omit unless this phase brief is intentionally limited to specific waves
ticket: "{ticket_id or ''}"  # omit for project-scoped briefs
parent_brief: "{parent_brief_path or ''}"  # phase/ticket briefs should point at the broader governing brief when one exists
captured: {now}
agent: creative-brief
tags: [creative, brief, planning]
---

# Creative Brief — {task_description}

## Client
{name}, {industry}, {location}

## Objective
{what we're building and why}

{For phase-scoped briefs, state the phase boundary explicitly: what this phase is proving, what it inherits from the project brief, and what it is NOT trying to prove yet.}

## Audience
{who will see/use this}

## Research Context Used

- **Snapshot path:** {research_context_path or "not available"}
- **Confidence:** {low_confidence false/true or "not available"}
- **Claim IDs used:** {cited research-context claim IDs used in references, quality bar, tooling, anti-patterns, media strategy, proof strategy, or Executability Audit}
- **Claim IDs treated as assumptions:** {low-confidence or inferred claim IDs used only as assumptions or risks, or "none"}

## References
1. {URL} — {what's good about it}
2. {URL} — {what's good about it}
3. {URL} — {what's good about it}

## Playbook Usage Contract
{reuse mode, matched playbooks, safe imports, forbidden inheritance}

## Why This Cannot Just Be The Playbook
{what is materially different here, what the old work does not prove, what must be originated or re-proven}

## Mission Alignment Map
{Extract every non-negotiable goal/workstream from the original client/admin request. Map each to acceptance criteria. This table is the primary input for the Mission Completion Gate at delivery.}

| Mission Goal / Workstream | Acceptance Criteria | How Verified | Scale / Scope |
|--------------------------|--------------------|--------------|---------------|
| {exact goal from original request} | {specific, measurable criterion} | {test, measurement, or evidence method} | {what scale this criterion proves, e.g. "3,578-file Chromium shard" vs "full 490K-file Chromium repo" vs "154K-entity CPython"} |

{If any goal cannot be met, tag it [DESCOPED] in the table with the reason. State: "Admin approval required." Do not silently omit goals. If a goal will be partially met, tag it [PARTIAL-COVERAGE] with justification.}

## Proof Strategy

- **Rigor tier:** {inherits from Goal Contract unless this brief intentionally changes the proof posture}
- **Evaluator lens:** {who or what would most skeptically judge this work}
- **Proof posture:** {why a project brief is sufficient here, or why this phase/ticket supplement exists}
- **Primary evidence modes:** {runtime proof, screenshots, citations, walkthrough, manual review, external validation, etc.}
- **False-pass risks:** {ways this could look done without being trustworthy}
- **Adversarial / skeptical checks:** {what should try to falsify or challenge the work}
- **Rehearsal lenses:** {which realistic users/reviewers/stakeholders should be simulated before risky transitions}
- **Drift sentinels:** {what would indicate the proof/docs/review surface drifted out of truth over time}
- **Supplement trigger:** {when a phase brief, wave supplement, or narrower proof packet becomes necessary}
- **Gate impact:** {which gates/QC/reviews depend on this proof strategy}

## Deliverable Contract
- **Outputs:** {exact files/artifacts to produce}
- **Structure:** {sections, sequence, or packaging expectations}
- **Acceptance Criteria:** {specific measurable checks}
- **Proof Standard:** {citations, screenshots, calculations, validations, or evidence required}
- **Failure Modes to Avoid:** {what would make this feel generic, thin, misleading, or incomplete}

## Runtime Acceptance Test
For each deliverable, specify how to verify it works from the user's perspective:
| Deliverable | Target Runtime | Test Procedure | Pass Criteria |
|-------------|----------------|----------------|---------------|
| {e.g., game build} | {e.g., Godot HTML5 export → browser} | {e.g., export, `agent-browser --allow-file-access open`, snapshot -i, click Start ref} | {e.g., gameplay loads, no console errors for 10s, player can move} |

## Verification Protocol

The executable proof that this deliverable works. QC and self-review MUST execute every command below and verify the expected output before issuing a verdict. A code/software deliverable that has not been verified through this protocol cannot receive PASS. For static deliverables, write "Covered by Runtime Acceptance Test" and omit the tables below. Refer to [[deliverable-standards]] Verification Protocol Reference for the appropriate proof methods per deliverable type.

### Build Verification
| Step | Command | Expected Result |
|------|---------|-----------------|
| {e.g., Install dependencies} | {e.g., `cd /path && npm install`} | {e.g., exit code 0, no errors} |
| {e.g., Compile backend} | {e.g., `cargo build --release`} | {e.g., exit code 0, binary at target/release/app} |

### Test Execution
| Suite | Command | Expected Result |
|-------|---------|-----------------|
| {e.g., Rust unit tests} | {e.g., `cargo test`} | {e.g., all pass, 0 failures} |
| {e.g., Frontend tests} | {e.g., `npm test -- --watchAll=false`} | {e.g., all pass} |

### Functional Proof
| Proof | Command/Procedure | Expected Result |
|-------|-------------------|-----------------|
| {e.g., App launches} | {e.g., `./target/release/app &` then screenshot} | {e.g., main window visible, no crash for 10s} |
| {e.g., Core workflow} | {e.g., connect to database, run query, view results} | {e.g., results render correctly} |

### Regression Anchor (for phase gates)
{Subset of the above that must pass at EVERY phase gate, not just final QC:}
- Build Verification: all steps
- Test Execution: {specify which suites are required per phase}
- Functional Proof: {specify which proofs are required per phase}

### Domain-Specific Verification
{Only if applicable. For non-code deliverables:}
| Claim/Element | Verification Method | Expected Result |
|---------------|--------------------|-----------------|
| {e.g., Case citation} | {e.g., Search CourtListener} | {e.g., case exists, year matches} |

## Presentation Direction
- **Palette:** {primary hex}, {secondary hex}, {accent hex}
- **Typography:** {heading font} / {body font}
- **Imagery style (global default):** {photography / illustration / 3D / abstract} — this sets the overall visual direction. Individual assets in the Media Specification table can override this when needed (e.g., global style is photography but one section uses an SVG illustration).
- **Layout:** {philosophy}

## Media Specification
*(Include only when the deliverable requires non-text assets to meet the quality bar. Omit for pure data, tools, or text-only deliverables.)*

Every row in this table is a **required deliverable asset** — not a suggestion. QC must verify each asset exists, matches the spec, and is integrated into the final output. A missing or downgraded media asset is a QC failure.

| Location | Subject | Type | Style | Dimensions/Format | Source Strategy | Fallback |
|----------|---------|------|-------|--------------------|-----------------|----------|
| {e.g., hero background} | {description} | {image/video/audio/animation/data-viz/3D} | {photo/illustration/motion/generative} | {e.g., 1920x800 WebP, 16:9 MP4 15s, WAV 30s} | {stock photo MCP/AI image MCP/Remotion/source-audio/Blender/SVG+CSS/client-provided} (note if MCP is available or planned) | {fallback if source unavailable} |

## Content Direction
- **Tone:** {description}
- **Headlines:** {approach}
- **CTA:** {primary goal}

## Quality Bar
{specific, measurable criteria for what "good" looks like}

## Recommended Tooling
- {plugins, MCPs, skills, or packages to use — e.g., "Use frontend-design plugin", "Use existing blender-automation MCP from archive"}

## Technical Requirements
{responsive, performance, accessibility specifics}

## Enterprise Validation Plan
Per [[deliverable-standards]] Enterprise Quality Gate. All fields below are mandatory for client work.
**Ground truth:** {what independent reference will validate correctness — e.g., "Compare entity counts against pyright/Sourcegraph," "Cross-reference data against Bureau of Labor Statistics," "Lighthouse scores against competitor sites." For novel tools with no reference: define a hand-verified golden dataset.}
**Breadth testing:** {how many varied inputs/scenarios — e.g., "5+ real-world Python repos from 10K-500K LOC," "3+ datasets with different encodings," "5 browsers + screen reader + 3G throttle"}
**Failure scenarios:** {at least 2 forced failure tests — e.g., "Kill indexer mid-run and verify resume," "Feed malformed YAML config and verify error message," "Disconnect network during API call and verify retry"}
**Known limitations to document:** {what boundaries and failure modes must be documented in the deliverable — e.g., "Max supported LOC, unsupported language features, memory requirements at scale." This becomes the README/LIMITATIONS.md section. QC will fail deliverables with no documented limitations.}
**Performance targets:** {what to measure and at what scale — e.g., "Index 500K LOC in <2h, peak memory <4GB," "Lighthouse performance >90," "Processing 100K rows in <60s." Include measurement command and hardware baseline.}
**Security requirements:** {what to audit — e.g., "Zero critical/high vulnerabilities in pip audit," "No eval/exec on user input," "All credentials from env vars." Reference OWASP Top 10 for web deliverables.}
**Recovery strategy:** {checkpoint/resume for read-only tools, atomic rollback for mutating tools, N/A for static deliverables — e.g., "Indexer checkpoints to SQLite every 1000 files, resume on restart," "Refactoring uses git branches — abort reverts to original branch"}

## Anti-Patterns to Avoid
- {specific thing NOT to do — e.g., "no stock photo grids," "no Lorem ipsum," "no default Bootstrap look"}
```

**Length discipline:**
- Project briefs can be comprehensive.
- Phase briefs should usually be **1-3 pages** and focus on the delta:
  - what this phase is proving
  - what evidence it must produce
  - what would make this phase fail
  - what the next phase needs from it
- Ticket briefs should be even narrower.

### Step 5: Attach to Ticket

1. Link the brief path in the relevant build ticket(s), self-review ticket, and quality-check ticket work logs.
2. The executor MUST read this brief before starting work. At each phase gate, the executor MUST run the Verification Protocol's Regression Anchor commands (if defined) and save evidence as a snapshot: `{date}-phase-{N}-verification-evidence.md` with command, exit code, output excerpt, and pass/fail status for each anchor step.
3. **Project-scoped briefs are the default** for onboarding and any project with a standalone `Creative brief` ticket. They govern all downstream execution/review tickets unless a later phase-scoped or ticket-scoped supplement narrows them.
4. **Phase-scoped briefs are supplements, not replacements.** When a phase brief exists, downstream tickets for that phase should read both:
   - the governing project brief
   - the phase brief addendum
   The phase brief wins only where it is more specific.
   The same applies to Proof Strategy: the phase brief should usually change only the proof lens or evidence package for that phase, not redefine the whole project mission.
4a. **Wave-limited phase briefs must say so mechanically.** If a phase brief only governs certain capability waves, set `covered_waves` in frontmatter (for example `["Wave 2A"]`). Later waves should not inherit that brief silently.
5. Ticket-scoped briefs are the narrowest exception: a specific sub-deliverable, channel, or artifact that truly needs its own bar. Ticket briefs supplement the project/phase brief stack rather than discarding it.
5a. **Phase/ticket briefs cannot be the first brief on a serious project.** If there is no project-scoped brief yet, create the project-scoped brief first and gate it normally before treating any narrower brief as authoritative.
6. QC checks deliverables against the brief's quality bar, not just functional requirements.

## When to Use

- **Always** before building a website, landing page, deck, report, presentation, campaign, or any client-facing deliverable
- **Always** before creating marketing content or communication templates
- **Always** before producing 3D renders, animations, or creative assets
- **Use the project-level mode by default** when the project has an explicit `Creative brief` ticket
- **Use phase-level mode** when a later phase has a materially distinct evaluation lens, proof contract, artifact contract, or anti-pattern set (verification, adversarial stress, artifact polish, delivery packaging, etc.)
- **Use ticket-level mode only** when a sub-deliverable needs a materially different spec
- **Platform/internal projects are allowed** when the work still has a real audience and a quality bar (marketing, landing pages, demos, branded docs)

## Principles

- **Research before creating.** 10 minutes of reference gathering saves hours of mediocre iteration.
- **Be specific.** "Make it look good" is not a brief. "Warm earth tones, generous whitespace, editorial typography, hero image with depth of field" is a brief. So is "Deliver a stock deck with a one-slide thesis per ticker, explicit downside risks, and a clear evidence trail."
- **Set the bar high.** The quality bar should describe work you'd be proud to put in a portfolio, not work that merely satisfies a checkbox.
- **Name what to avoid.** Anti-patterns are as important as aspirations. "No generic stock photos" prevents the most common failure mode.
- **Research-context is input, not proof.** A research-context claim that a capability exists is not enough for a PASS row; the brief must show that the capability is available in this run.
- **Use currentness findings surgically.** Deprecated-pattern findings should appear in anti-patterns or be explicitly dismissed, and current version findings must prevent stale recommended-tooling claims.
- **Keep the existing gate model.** No separate gate-review subagent is added for research-context; the Executability Audit remains the proof boundary.

## See Also

- [[self-review]]
- [[quality-check]]
- [[gather-context]]
- [[match-playbooks]]
- [[orchestrator]]
