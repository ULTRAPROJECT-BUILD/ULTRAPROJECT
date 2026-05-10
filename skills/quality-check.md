---
type: skill
name: quality-check
description: Final verification of deliverables before client delivery — confirms artifacts exist, meet requirements, and are production-quality
inputs:
  - client (optional — client slug; required for client-scoped delivery projects)
  - project (required — project slug)
  - deliverables_path (optional — path to the deliverables directory; if omitted, infer from the project/tickets)
  - requirements (optional — what the client asked for; if omitted, infer from clarification tickets, project notes, and snapshots)
  - creative_brief_paths (optional — ordered applicable brief path(s); if omitted, resolve from project snapshots by matching project / phase / ticket briefs)
---

# Quality Check

You are the final gate before work is delivered to a client. Nothing ships until this skill passes. Your job is to verify that every promised deliverable actually exists, works, and meets the client's requirements.

**Mindset:** Assume nothing. Do not trust prior agents' reports. Verify everything yourself by reading files, running code, and checking output.

## Process

### Step 0: Determine Scope

1. Read the project file for `{project}` first.
2. Resolve whether this is:
   - A client-scoped delivery project (`client` provided, or the project lives under `vault/clients/{client}/projects/`)
   - A platform/internal project
3. Resolve `deliverables_path`:
   - If provided explicitly, use it.
   - If omitted for a client-scoped project, look for a documented deliverables directory in the project notes, ticket results, or default to `vault/clients/{client}/deliverables/`.
   - If omitted for a platform project, infer it from the project notes/tickets. If no concrete artifact path can be determined, stop with **FAIL — Incomplete** and create a ticket to document the deliverables path before delivery.
4. Resolve `requirements`:
   - If provided explicitly, use them.
   - Otherwise read the clarification/discovery ticket, the project goal/notes, and any relevant incoming snapshots to build the checklist of promised outputs.
5. Resolve applicable creative briefs:
   - If `creative_brief_paths` is provided, use those.
   - Otherwise, gather snapshots tagged `creative` / `brief` for this project.
   - Prefer a **project-scoped** brief first (matching `project` and intended to govern the whole delivery set).
   - Then gather any **phase-scoped** supplements for the current phase.
   - Then gather any **ticket-scoped** supplements whose frontmatter `ticket` matches a creative/build/review ticket in the project's task list.
   - Treat the project-scoped brief as the default source of truth. Phase-scoped and ticket-scoped briefs only narrow or extend it for the specific phase / sub-deliverable they govern.
   - Resolution order is: project brief -> phase brief -> ticket brief. More specific briefs override broader ones on conflict.
   - If the project includes branded, polished, analytical, or otherwise client-facing deliverables and no applicable brief exists, this is not a PASS. Flag at least **REVISE** and create a creative brief ticket so the work has a defined quality bar.
6. Resolve the QC report path:
   - Client-scoped: `vault/clients/{client}/snapshots/{project}/{now}-qc-report-{project}.md`
   - Platform-level: `vault/snapshots/{project}/{now}-qc-report-{project}.md`

### Step 1: Inventory Check

1. List all files in `{deliverables_path}` recursively.
2. Compare against the requirements — for every deliverable the client was promised, confirm:
   - The file exists
   - The file is not empty (size > 0)
   - The file type matches expectations (e.g., `.html` for a website, `.png` for renders)
3. **If any promised deliverable is missing:** FAIL immediately. Create a ticket to produce the missing item, add it to the project task list, and do NOT proceed to delivery.

### Step 1b: Browser Tool Routing

This skill uses two browser tools for different purposes. Choose the right one:

| Task | Tool | Why |
|------|------|-----|
| Visual screenshot (full-page capture for inspection) | `agent-browser` | Token-efficient, annotated screenshots map refs to elements |
| CDN/asset load verification | `agent-browser` | Navigate + snapshot confirms page loaded, check network requests |
| Form filling, clicking, navigation smoke test | `agent-browser` | Ref-based interaction is deterministic, batch execution reduces overhead |
| Interactive element discovery | `agent-browser` | `snapshot -i` returns only interactive elements with refs (~400 tokens vs ~4,000) |
| Mobile/responsive viewport testing | `agent-browser` | `set device "iPhone 14"` or `set viewport W H` — built-in device emulation |
| iOS simulator testing | `agent-browser` | `-p ios --device "iPhone 16 Pro"` — only tool with native iOS support |
| **JS-disabled graceful degradation** | **Playwright Python API** | agent-browser cannot disable JS — Playwright browser context required |
| **Console error capture** (page.on listeners) | **Playwright Python API** | agent-browser `console` command exists but Python event listeners are more reliable for structured capture |
| **JS state injection** (read game/app state before/after input) | **Playwright Python API** | Complex page.evaluate with closures, state comparison logic |
| **Multi-context testing** (same page, different configs) | **Playwright Python API** | Multiple browser contexts with different settings |

**Default to `agent-browser`** unless the task specifically requires Playwright Python API capabilities listed above. This saves ~16x tokens per browser interaction.

**agent-browser commands used in QC:**
```bash
agent-browser open "file://{path}"              # Navigate to local file
agent-browser --allow-file-access open "file://{path}"  # Required for local files
agent-browser wait --load networkidle           # Wait for page to fully load
agent-browser screenshot "{path}" --full        # Full-page screenshot
agent-browser screenshot "{path}" --annotate    # Screenshot with numbered element labels
agent-browser snapshot -i                       # Interactive elements with refs
agent-browser click @e1                         # Click by ref
agent-browser fill @e2 "text"                   # Fill input by ref
agent-browser get text @e1                      # Extract element text
agent-browser network requests                  # Check HTTP requests (CDN verification)
agent-browser eval "document.querySelectorAll('img[src]').length"  # JS evaluation
agent-browser close                             # Always close when done
```

### Step 2: Artifact Validation

For each file type, run the appropriate checks:

**HTML/CSS/JS websites:**
- Open and verify valid HTML structure (`<html>`, `<head>`, `<body>`)
- Check that referenced assets (images, CSS, JS) exist locally or are valid external URLs. **For CDN dependencies:** verify each external script/stylesheet URL returns HTTP 200 before proceeding — build agents are known to hallucinate CDN version numbers (e.g., referencing a non-existent library version). A CDN 404 produces a blank page that is invisible to code review. Browser load test is mandatory for any deliverable with CDN dependencies. (Learned from 2026-03-18-qc-pipeline-catches-cdn-version-bugs, 2026-03-18)
- Verify the page isn't just boilerplate/placeholder — it should contain client-specific content
- **Visual screenshot test (mandatory for websites):** Use `agent-browser` for the full-page screenshot:
  ```bash
  agent-browser --allow-file-access open "file://{absolute_path_to_index.html}"
  agent-browser wait --load networkidle
  agent-browser screenshot "{deliverables_path}/qc-screenshot-full.png" --full
  agent-browser close
  ```
  Then read the screenshot image to verify:
  - All sections are visible (not blank/hidden by CSS)
  - Images are rendering (not broken image icons or empty boxes)
  - Layout looks professional, not broken or overlapping
  - Client branding is present
- **Ownership rule:** QC owns runtime screenshot capture for user-visible browser/native work unless the brief explicitly assigned it earlier. If the screenshots are missing, that is a QC defect, not a documentation footnote.
- **Walkthrough video (MANDATORY for interactive web deliverables, recommended for motion-heavy marketing surfaces):**
  First try the auto-capture helper:
  ```bash
  python scripts/ensure_qc_walkthrough.py \
    --deliverables-root "{deliverables_path}" \
    --brief "{creative_brief_path}" \
    --qc-report "{qc_report_path}" \
    --url "http://localhost:3000" \
    --json-out "{deliverables_path}/qc-walkthrough-report.json"
  ```
  If QC already knows the runtime URL, use `--url`. If the helper cannot infer a stable route and returns non-zero for a required walkthrough, that is a QC defect unless the report explicitly explains why the UI was not capturable.

  Manual fallback:
  ```bash
  python scripts/capture_walkthrough_video.py web \
    --url "http://localhost:3000" \
    --output "{deliverables_path}/qc-walkthrough.mp4" \
    --duration 8 \
    --scroll
  ```
  Capture this after the automated smoke path passes. For dashboards, web apps, admin surfaces, multi-step flows, or any browser deliverable where motion/state transitions matter, missing `qc-walkthrough.mp4` is a QC defect. Cite the video filename in QC findings.
- If upstream stages were supposed to produce benchmark/design screenshots (for example Stitch comparison artifacts), verify those files exist and cite them too. Missing upstream-owned artifacts should block the producing stage; missing QC-owned artifacts should block QC.
- **Graceful degradation check:** Verify the page is usable with JavaScript disabled. This requires **Playwright Python API** (agent-browser cannot disable JS):
  ```bash
  python -c "
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
      browser = p.chromium.launch()
      ctx = browser.new_context(java_script_enabled=False, viewport={'width': 1440, 'height': 900})
      page = ctx.new_page()
      page.goto('file://{absolute_path_to_index.html}')
      page.screenshot(path='{deliverables_path}/qc-screenshot-nojs.png', full_page=True)
      browser.close()
  "
  ```
  Compare the no-JS screenshot to the full screenshot. If sections are blank or invisible without JS (e.g., CSS `opacity: 0` that JS is supposed to reveal), flag this as **FAIL — Broken**. Content must be visible by default. **Exception:** JS-heavy web apps (React, Vue, dashboards, games-in-browser) inherently require JS — skip this check for those. See [[deliverable-standards]].
- **If the repo already ships Playwright tests:** run those with `npx playwright test` (or the package script wrapper) as the canonical browser QA path. Use that result as the primary pass/fail evidence, then use `agent-browser` and walkthrough capture as complementary QC evidence.
- **Do not plan around Playwright MCP:** the old MCP path is no longer active in this system. Use `agent-browser` for interactive smoke checks and the Playwright Python API only when a deeper one-off browser probe is required.
- **Packaging check:** If files will be zipped for operator-mediated delivery, verify that any channel-specific file renaming is documented in the delivery handoff with clear rename instructions.

**CSS files:**
- Verify non-empty and parseable
- Check that class/ID selectors match those used in the HTML
- Flag any `opacity: 0` or `display: none` on content sections that rely on JS to become visible

**JavaScript files:**
- Run a syntax check: `node --check {file}` or equivalent
- Verify it's not just boilerplate
- Check that scroll-reveal or animation code has a fallback (content visible without JS)

**PPTX / Slides / Documents:**
- **Visual slide rendering (mandatory for presentations):** Convert every slide to an image and visually inspect each one. Programmatic checks (file size, structure, statistics) are NOT sufficient — shapes can overlap text, elements can overflow, and z-order bugs are invisible without rendering. Run:
  ```bash
  # Install rendering tools if not available
  # LibreOffice exposes 'soffice' on macOS, 'libreoffice' on Linux
  which libreoffice || which soffice || brew install --cask libreoffice
  which pdftoppm || brew install poppler

  # Derive PDF filename from PPTX path (e.g., my-deck.pptx → my-deck.pdf)
  # Convert PPTX to PDF
  PPTX_PATH='{pptx_path}'
  PDF_NAME="$(basename "$PPTX_PATH" .pptx).pdf"
  libreoffice --headless --convert-to pdf --outdir /tmp/ "$PPTX_PATH" \
    || soffice --headless --convert-to pdf --outdir /tmp/ "$PPTX_PATH"

  # Convert PDF to per-slide PNGs (pdftoppm is mandatory — do NOT use sips, it only renders one page)
  mkdir -p '{deliverables_path}/qc-slides'
  pdftoppm -png -r 200 "/tmp/$PDF_NAME" '{deliverables_path}/qc-slides/slide'
  ```
  **Verify slide count:** Count the generated PNGs and compare against the number of slides in the PPTX (via python-pptx `len(prs.slides)`). If counts don't match, the conversion failed partially — flag and investigate.
  Then **read each slide image** and verify:
  - No shapes or decorative elements overlapping text content (z-order issues)
  - No text cut off or overflowing outside slide bounds
  - All text is readable (sufficient contrast against backgrounds)
  - Layout matches the intended design — elements are properly positioned
  - Brand colors and fonts are applied correctly
  - Embedded images are visible and correctly placed
  - No blank or broken slides
- **Cross-application check:** If possible, verify the file opens correctly in the target application (Google Slides, PowerPoint, Keynote). At minimum, verify python-pptx can re-read all shapes without errors.
- Verify file size is reasonable
- Check all slides have content (no empty slides)

**Image files (PNG, JPG, etc.):**
- Verify the file is a valid image (not 0 bytes, not corrupted)
- Check dimensions are reasonable for the use case (e.g., hero images should be at least 1200px wide)
- If the image was supposed to be a 3D render, verify it's not a placeholder or solid color
- Take a screenshot or read the image to visually confirm it contains meaningful content

**Video/animation files (MP4, WebM, etc.):**
- Verify the file is a valid video (not 0 bytes, has duration)
- Check resolution and duration are reasonable for the use case
- Verify it plays (use `ffprobe` or similar to check codec/format)

**Code files (Python, etc.):**
- Syntax check
- If it's an MCP server, do NOT just check syntax and imports. Run the full [[test-mcp-server]] protocol: startup test, tool invocation, error handling, and artifact verification. A structurally correct but nonfunctional MCP is a FAIL.

**Zip/archive files:**
- Verify the archive is valid and can be extracted
- List contents and verify expected files are inside

### Step 2b: Runtime Verification (MANDATORY)

**Verification Manifest Gate (MANDATORY for code/software deliverables):**
Before running runtime verification, check for a verification results file in the project's snapshots directory (glob `*verification-results*{project}*` or legacy `*test-manifest-results*{project}*`).

- If the project has a creative brief and produces a code/software deliverable:
  - **No verification results exist:** FAIL — Incomplete. The Build-Prove-Fix Loop did not run. Create a ticket to generate and execute the verification manifest via [[test-manifest]].
  - **Verification results exist but EXECUTABLE P0 pass rate < 100%:** FAIL — Broken. The Build-Prove-Fix Loop did not complete. Create fix tickets for remaining CODE_DEFECT items.
  - **Verification results exist and 100% EXECUTABLE P0 + P1:** Proceed to runtime verification below.
  - **Results timestamp older than 24 hours:** FAIL — Stale. Re-run the verification manifest.
  - **Proof matrix is missing or collapsed into a single blended "test count":** REVISE. The report must distinguish automated tests, build checks, runtime proofs, inspection checks, artifact checks, external validations, and manual review items.
- For non-code deliverables (documents, presentations, images, data): skip this check.

**Every deliverable must be tested in its target runtime from the user's perspective.** File existence and code review are necessary but never sufficient. If the user would open it and it doesn't work, it's broken — period.

Read the creative brief's "Target runtime and user acceptance test" section. For each deliverable, execute the specified test. If no brief exists, determine the target runtime yourself:

| Deliverable Type | Target Runtime | How to Verify |
|-----------------|----------------|---------------|
| HTML website | Browser | `agent-browser`: open page, screenshot, snapshot -i for interactive elements, click/fill smoke test. Use Playwright Python API only for JS-disabled testing and console error capture. |
| Godot project | Godot engine | Export to HTML5: `godot --headless --export-release "Web" /tmp/export/index.html` → `agent-browser --allow-file-access open "file:///tmp/export/index.html"` → screenshot → snapshot -i → click Start ref → check for errors. If export fails, the project is broken. |
| Python script/tool | Python | Run with sample inputs: `python tool.py --help` or test command → verify exit code 0, check stderr for errors |
| Node.js app | Node | `node app.js` or `npm start` → verify it starts, hit endpoints if applicable |
| MCP server | MCP protocol | Run full [[test-mcp-server]] including tool invocation and artifact verification |
| PPTX/slides | LibreOffice + visual | Convert to PDF → per-slide PNGs via LibreOffice headless → read each slide image → verify no overlapping shapes, text overflow, or broken layouts. Programmatic checks alone are NOT sufficient. |
| PDF/document | Preview/reader | Open with `open` or `qlmanage -p` → verify it renders, check page count |
| Mobile app (iOS) | iOS Simulator | `agent-browser -p ios --device "iPhone 16 Pro" open {url}` → snapshot -i → tap refs → screenshot. Requires Xcode + Appium. |
| Mobile app (Android) | Android Emulator | Build APK → launch in emulator → `agent-browser` connect via remote debugging → snapshot → tap → screenshot |
| Desktop app | Native OS | Launch the executable → verify main window, primary function, then run `python scripts/ensure_qc_walkthrough.py --deliverables-root {deliverables_path} --brief {creative_brief_path} --qc-report {qc_report_path} --json-out {deliverables_path}/qc-walkthrough-report.json` or fall back to `python scripts/capture_walkthrough_video.py desktop --output {deliverables_path}/qc-walkthrough.mp4 --duration 8` for any reviewable UI flow |
| API | HTTP | Hit endpoints with curl/requests → verify responses match spec |
| Data/CSV | Pandas or viewer | Load and verify: row count, column names, no parse errors, sample values make sense. Check against [[deliverable-standards]] for the Data/CSV type. |
| Game (any engine) | Engine + browser | Full playthrough verification — see **Game Quality Playthrough** below. Use `agent-browser` for navigation/screenshots, Playwright Python API for state injection and console capture. |

**Rules:**
1. If the runtime test fails (crash, error, blank screen, broken functionality), the verdict is **FAIL — Broken** regardless of how clean the code looks.
2. If you can't run the test (missing dependency, no export template, etc.), install what's needed. You're a self-extending agent — `brew install`, `pip install`, download the export template, whatever it takes.
3. If after best effort you truly cannot test it automatically, create a **mandatory** human-review ticket with exact steps for manual testing. Do NOT mark QC as PASS. Use **PASS with caveats** and list what couldn't be verified.
4. Log all runtime proof results with evidence: exit codes, screenshots, walkthrough video filenames, console output, error messages. For interactive browser/native deliverables, the QC report must cite the walkthrough filename explicitly.
5. **Step 2b is necessary but not sufficient for code/software deliverables.** A binary that launches is not proof that it works correctly. Step 2d (Verification Protocol Execution) provides the full proof chain. Do not skip 2d because 2b passed.

### Step 2c: Game Quality Playthrough (MANDATORY for all game deliverables)

**"Verify main menu loads" is NOT sufficient QC for a game.** The agent must play through the entire game start-to-finish and verify visual quality, audio, mechanics, and polish at every stage. A game that compiles and runs but looks like a graybox prototype is a FAIL — the same way a PPTX that has correct data but shapes covering text is a FAIL.

**Process:**

1. **Export to testable format** — HTML5 via `godot --headless --export-release "Web"` (preferred for `agent-browser` automation) or launch directly in the engine editor.

2. **Visual quality walkthrough** — screenshot at EVERY distinct area/encounter in the game. For each screenshot, verify:
   - Textures are applied to ALL surfaces (no untextured gray/white geometry)
   - Lighting is active and creates atmosphere (shadows, ambient, directional — NOT flat uniform lighting)
   - Models are the final assets, not CSG primitives or graybox placeholders
   - VFX are visible when triggered (muzzle flash on shoot, impact particles on hit, shell casings)
   - UI/HUD elements are present and readable (health, ammo, crosshair, objective markers)
   - **If anything looks like a developer prototype rather than a finished game, it's FAIL — Incomplete**

3. **Audio verification** — verify audio is wired into the game, not just that files exist in the project:
   - Check that audio manager/autoload scripts reference the audio files
   - Check that gameplay scripts trigger audio events (weapon fire, footsteps, enemy sounds, UI)
   - If testing via HTML5 export: check Web Audio API context is active and audio nodes are created during gameplay (use `agent-browser eval` or Playwright Python API)
   - If testing headlessly and audio cannot be directly verified: verify code paths exist for ALL expected audio categories AND that audio files are imported into the engine project (not just in a raw/ folder). Note as "code-verified, not runtime-verified" — acceptable for **PASS with caveats** only, never a clean PASS. Create a human-playtest ticket for runtime audio verification.
   - **Audio files that exist in the project but aren't wired into any script = FAIL — Incomplete** (same as models that exist but aren't in the level)

4. **Mechanics playthrough** — play through every level/encounter/stage sequentially. Adapt checks to the game's genre (read the creative brief to identify core mechanics):

   **For FPS/action games:** movement (WASD, sprint, crouch, jump), weapons (fire, reload, switch, recoil feedback), enemies (spawn, AI behavior, damage, death), damage (health system, player death, respawn), pickups, win/lose conditions.

   **For puzzle/strategy games:** core puzzle mechanic works, solutions are achievable, difficulty progression, UI for game state, undo/reset, win detection.

   **For narrative/adventure games:** dialogue system, scene transitions, choice branching, inventory, save/load state.

   **For any genre — universal checks:**
   - Can you play from start to finish without softlocks?
   - Does every core mechanic respond to input?
   - Is there a clear win/lose/end state?
   - Can you restart after completion or death?

5. **Polish checklist** — these are the difference between "it runs" and "it feels good":
   - [ ] No Z-fighting (flickering surfaces where geometry overlaps)
   - [ ] No clipping (player/enemies walking through walls or objects)
   - [ ] No floating objects (props not grounded on surfaces)
   - [ ] No invisible walls without visual indication
   - [ ] Frame rate stable (no obvious stuttering during normal gameplay)
   - [ ] Camera doesn't clip through geometry when near walls
   - [ ] All text in UI is readable and not overlapping

6. **Evidence** — save screenshots from each encounter, a screenshot of the main menu, and screenshots of any issues found. Include all in the QC report.

7. **Verdict impact:**
   - Graybox/untextured geometry visible in final build → **FAIL — Incomplete** (assets exist but weren't integrated)
   - No audio playing → **FAIL — Incomplete**
   - Core mechanic broken (can't shoot, can't move, enemies don't work) → **FAIL — Broken**
   - Softlock (can't progress past an encounter) → **FAIL — Broken**
   - Polish issues only (minor clipping, occasional Z-fight) → **REVISE**
   - Everything works, looks finished, sounds right → **PASS**

(Learned from 2026-03-20: Blender x Godot FPS generated 19 models, 43 audio files, 2 shaders, and 13 VFX scenes but shipped as a graybox because QC only verified "headless tests pass" and never looked at the running game. The assets existed but weren't wired into the level.)

### Step 2d: Verification Protocol Execution (MANDATORY)

**Every deliverable with a Verification Protocol in its creative brief MUST have that protocol executed before QC can issue any verdict other than FAIL.**

This step is distinct from Step 2b (Runtime Verification). Step 2b verifies the deliverable runs from the user's perspective. Step 2d verifies the full engineering proof chain: build from source, run test suites, execute functional proofs, and perform domain-specific verification. A Tauri app might pass Step 2b (the built binary launches) but fail Step 2d (the Rust tests have 12 failures).

**Process:**

1. **Locate the protocol.** Read the creative brief's `## Verification Protocol` section. If no protocol exists:
   - For code/software deliverables with a brief created on or after 2026-03-23: **FAIL — Incomplete** (the brief is defective). Create a ticket to add the protocol.
   - For code/software deliverables with a LEGACY brief (before 2026-03-23): use the Runtime Acceptance Test section as the verification method. Note "Legacy brief — using Runtime Acceptance Test as verification protocol" and proceed with best-effort build/test execution based on the project's build system.
   - For static deliverables (HTML, PDF, presentations, images, video) where Step 2b provides full runtime verification: note "Verification Protocol: covered by Step 2b runtime verification" and proceed.
   - For knowledge deliverables (legal, research, medical, engineering, financial): if no Domain-Specific Verification section exists, proceed but note the gap. Create a human-review ticket for domain expert verification.

2. **Execute Build Verification.** Run every command in the Build Verification table.
   - Record each command, actual exit code, and stderr output.
   - If ANY build step fails: **FAIL — Broken**. Do not proceed to test execution.
   - Save build log as evidence.

3. **Execute Test Suites.** Run every command in the Test Execution table.
   - Record suite name, command, exit code, pass/fail counts, failure messages.
   - If failures in core functionality: **FAIL — Broken**. Minor flaky tests in edge cases: **REVISE**.
   - Save test output as evidence.

4. **Execute Functional Proofs.** Run every command/procedure in the Functional Proof table.
   - For CLI proofs: run command, capture output, verify against expected.
   - For GUI proofs: use the runtime-appropriate tool per the Critical Flow Verification tool table in [[deliverable-standards]]. **Web/browser apps:** `agent-browser` for visual screenshots, Playwright for interactive flow assertions. **Tauri (Windows/Linux):** `tauri-driver` WebDriver. **Tauri (macOS):** `tauri-webdriver` (community) if available, otherwise Computer Use MCP as fallback. **Electron:** Playwright Electron API. **Other native desktop:** Computer Use MCP. Prefer programmatic WebDriver/Playwright tools over Computer Use — they are 1000x more token-efficient and produce the same functional evidence. Computer Use MCP is the fallback when no programmatic automation exists for the platform. Save screenshots to `{deliverables_path}/` as `qc-screenshot-{proof-name}.png`. Create the directory if needed (`mkdir -p`). Reference the screenshot path in the Functional Proof results table. A functional proof for a visual deliverable without a screenshot is not proof — it's a claim.
   - For API proofs: use `curl` or Python requests, capture response, verify.
   - If ANY functional proof fails: **FAIL — Broken**.

5. **Execute Domain-Specific Verification** (if the protocol includes it).
   - **Citation verification:** For each citation, search the specified source (CourtListener API, Google Scholar, PubMed, DOI resolver). Record: citation text, source searched, found (yes/no), metadata match (yes/no). Log results in a table.
   - **Calculation verification:** For each calculation, extract inputs and formula, compute independently (Python `eval` or calculator), compare. Record: calc ID, inputs, expected, actual, delta, pass/fail. Must match within stated tolerance or ±0.1%.
   - **Data verification:** For each claimed statistic, fetch the original source URL, locate the number, compare. Record: claim, source URL, source value, match (yes/no).
   - **Reference checking:** For each URL/DOI, verify HTTP 200 or DOI resolution. Record: reference, status code, accessible (yes/no).
   - Threshold: 100% of critical claims must verify. 90%+ for non-critical supplementary claims with unverified items flagged in the QC report.

6. **Record results** in the QC report under `## Verification Protocol Results`.

**Rules:**
- The protocol is not optional. If the brief defines one and QC skips it, the QC report is invalid.
- Build failures block test execution. Critical test failures block functional proof.
- If a protocol step requires a tool that isn't installed, install it (`brew install`, `rustup`, `apt-get`).
- If a step truly cannot be executed (requires proprietary hardware), note as "unverifiable" and create a human-review ticket. Use **PASS with caveats**, never clean PASS.

### Step 2e: Evidence Freshness and Consistency Check (MANDATORY)

**Do not trust evidence at face value.** Cross-check counts and timestamps across all evidence sources to catch stale or contradictory reports.

1. **Timestamp freshness:** Reject any screenshot or test result that is older than the most recent code change (check git log). Stale evidence means the tests ran against a different version of the code.
2. **Count consistency (same-scope comparisons only):** Cross-check test counts between sources that measure the same scope:
   - **Unit/integration test counts:** Compare QC's own `npm test` / `cargo test` run against the counts in the most recent runtime check report. These should be within 5% (minor variance from flaky tests is acceptable).
   - **Verification manifest counts:** Compare the verification-results pass/fail totals against the manifest's declared item count. If items are missing from the results, the execution was incomplete.
   - **Proof matrix consistency:** Compare the proof-summary counts against the full results rows. If the proof matrix says 5 `build_check` items but only 3 appear in results, the report is inconsistent.
   - **Do NOT compare** verification-manifest counts against unit test counts, or self-review regression checks against full test suite counts — these are intentionally different in scope.
   If same-scope counts diverge by more than 5%, flag as INCONSISTENT and investigate before proceeding.
3. **Screenshot staleness:** Verify screenshot files in the evidence directory have modification timestamps after the most recent code commit that changed the relevant files.
4. **If any evidence is stale or inconsistent:** Do not issue PASS. Re-run the stale/inconsistent checks. If re-running is not possible, use PASS with caveats and document exactly what could not be freshly verified.

### Step 2f: Codebase Validation via Knowledge Graph (existing-codebase projects only)

**This step only applies when the project file has `has_existing_codebase: true` AND a `.refactor-engine/` directory exists at `target_codebase_path`.** Skip entirely for greenfield projects or projects without an indexed codebase.

1. **Check preconditions:**
   - Read the project file's frontmatter. If `has_existing_codebase` is not `true`, skip this step.
   - Resolve `target_codebase_path` from the project frontmatter.
   - Check whether `{target_codebase_path}/.refactor-engine/` exists. If it does not, skip this step (the codebase has not been indexed yet — note in the QC report that knowledge graph validation was skipped due to missing index).

2. **Determine changed files for the current phase:**
   - Read closed tickets for this project in the current phase.
   - Collect file paths from each ticket's `file_paths` field or work log entries that reference modified files.
   - If no changed files can be determined, skip this step and note "No changed files identified for codebase validation" in the QC report.

3. **Run the bridge validate command:**
   ```bash
   python scripts/refactor_bridge.py validate \
     --target {target_codebase_path} \
     --changed-files {comma_separated_file_paths}
   ```
   Parse the JSON output. The bridge returns:
   ```json
   {
     "ok": true,
     "data": {
       "changed_files": [...],
       "entities_analyzed": N,
       "results": [
         {
           "entity": { "name": "...", "file_path": "...", "complexity_cyclomatic": N, "complexity_cognitive": N, ... },
           "blast_radius": [{ "entity": {...}, "depth": N, "relationship": "..." }, ...],
           "blast_radius_count": N,
           "callers": [...],
           "caller_count": N,
           "interface_violations": [...],
           "complexity_cyclomatic": N,
           "complexity_cognitive": N
         }
       ]
     }
   }
   ```

4. **Handle bridge failures gracefully:**
   - If the command exits non-zero or returns `"ok": false`, log the error message in the QC report under `## Codebase Validation` with a note: "Bridge validation failed: {error}. This does not block QC but should be investigated."
   - Do NOT fail the overall QC because the bridge errored. Continue to Step 3.

5. **Analyze results and include in QC report** as a `## Codebase Validation` section:

   ```markdown
   ## Codebase Validation

   **Source:** `refactor_bridge.py validate` against knowledge graph at `{target_codebase_path}`
   **Files checked:** {comma_separated_file_paths}
   **Entities analyzed:** {entities_analyzed}

   ### Interface Violations
   {For each entity with non-empty `interface_violations`: list the entity name, file, and violation details.}
   {If none: "No interface violations detected."}

   ### Blast Radius Summary
   | Changed Entity | File | Affected Entities | Max Depth |
   |---------------|------|-------------------|-----------|
   | {entity.name} | {entity.file_path} | {blast_radius_count} | {max depth from blast_radius items} |

   ### Complexity Deltas
   | Entity | File | Cyclomatic | Cognitive | Flag |
   |--------|------|------------|-----------|------|
   | {name} | {file} | {cyclomatic} | {cognitive} | {HIGH if cyclomatic > 15 or cognitive > 20} |
   ```

6. **QC finding escalation:**
   - **Interface violations** (non-empty `interface_violations` on any entity): Flag as a QC finding with `[SEVERITY: HIGH] [CATEGORY: wiring/integration]`. These indicate a changed entity's public API may break its callers. Create a fix ticket if violations are found.
   - **High blast radius** (any entity with `blast_radius_count > 20`): Flag as a QC finding with `[SEVERITY: MEDIUM] [CATEGORY: wiring/integration]`. Note the affected entity and recommend review of downstream consumers.
   - **High complexity** (any entity with `complexity_cyclomatic > 15` or `complexity_cognitive > 20`): Flag as a QC finding with `[SEVERITY: LOW] [CATEGORY: design-quality]`. Recommend refactoring if complexity increased significantly compared to the codebase average.

### Step 3: Requirements Match

Read the original client requirements (from the clarification ticket or project notes). For each requirement, verify:

1. **Was it addressed?** — Is there a deliverable that satisfies this requirement?
2. **Was it done correctly?** — Does the deliverable actually do what was asked? (e.g., "lead gen website" should have a contact form, "3D landscape renders" should show actual landscapes)
3. **Was anything missed?** — Are there requirements that no deliverable covers?

Create a checklist:
```
- [x] Portfolio website with hero section — index.html exists, has 5 sections
- [x] Contact/lead gen form — present in HTML with validation in JS
- [ ] 2-3 Blender landscape renders — NO IMAGE FILES FOUND → FAIL
- [x] Responsive layout — CSS has media queries
```

**HARD RULE: Any unchecked item in the approved mandatory scope is FAIL — Incomplete.**

Build the requirements checklist from the **approved scope**, not the raw original request:
1. Start with the creative brief's deliverable contract and scope matrix (if one exists). Items marked **IN** are mandatory. Items marked **OUT** (with client or admin approval) are excluded from the checklist.
2. If no scope matrix exists, use the client's explicit requirements from their clarification answers. Treat "I need X" as mandatory. Treat "if possible" or "nice to have" as optional.
3. Optional/wishlist items that aren't delivered are noted but don't trigger FAIL.
4. **Every mandatory item must be checked off or the verdict is FAIL — Incomplete.**

A "documented limitation" or "API doesn't support it" is not a PASS — it means the system needs to find another way (different API, different data source, different approach) or tell the client BEFORE delivering that this specific item can't be done and get their acknowledgment. The client decides whether to accept partial delivery, not the QC agent.

- 0% coverage on a mandatory requested column → **FAIL — Incomplete**, not "PASS with a note"
- "We tried but the API didn't have it" → create a ticket to try other sources, don't ship
- If truly impossible after exhausting all options → draft a client-facing limitation note and ask how to proceed BEFORE marking the delivery ticket as done

(Learned from 2026-03-18: Example Client requested website URLs, system delivered 199,549 rows with 0% URL coverage, QC passed it as "documented limitation," client flagged it immediately as missing key data.)

**Pre-delivery communication recommendation:** When QC identifies any mandatory requirement below target but the overall verdict is still PASS (e.g., partial coverage on a data column that the client may accept), the QC report MUST include a recommendation in the Action Required section: "Prepare a gap-disclosure handoff note for client approval before delivering." This ensures the delivery flow routes through client approval rather than surprising them with gaps. (Learned from 2026-03-18-pre-delivery-gap-communication, 2026-03-18)

### Step 4: Quality Review

Beyond "does it exist," assess whether the work is good enough to ship:

- **Deliverable standards compliance:** Read [[deliverable-standards]] for the relevant deliverable type(s). These are baseline professional standards that apply to ALL output — the brief sets the bar higher, never lower. A CSV with unformatted currency, a website with 12px body text, or a plain-text client communication artifact all violate standards regardless of what the brief says.
- **Visual quality:** Would this look professional to the client? Or is it obviously auto-generated placeholder content?
- **Completeness:** Are there TODO comments, placeholder text ("Lorem ipsum"), or missing sections?
- **Functionality:** Do forms work? Do links point somewhere valid? Do animations run? See **Step 4b: Automated Interaction Smoke Testing** below for interactive deliverables.
- **Client branding:** Does it use the client's business name, location, and industry appropriately?
- **Imagery content relevance:** Does every image, render, and visual asset depict the client's actual industry and product? Check that no assets from a different domain were force-fitted. A valid PNG from the wrong industry is a FAIL. (Learned from 2026-03-17-wrong-blender-scene-reused, 2026-03-17)
- **Creative brief compliance:** For each applicable brief, verify the deliverables match the specified palette, typography, imagery style, layout philosophy, CTA strategy, quality bar, and anti-patterns to avoid.
- **Analytical / research quality:** For research decks, analyses, or reports, verify the conclusions are supported by the cited evidence, that numbers are internally consistent, and that caveats/risks are stated clearly enough for a skeptical reader.
- **Operational / process quality:** For playbooks, SOPs, or system docs, verify the steps are executable in sequence, prerequisites are explicit, escalation paths are documented, and handoff language is concrete rather than vague.
- **Playbook overreach check:** For project plans, creative briefs, platform specs, and other frontier/high-novelty planning artifacts, verify that archived playbooks are used as bounded prior art rather than silent proof. Missing `Playbook Usage Contract` / `Why This Cannot Just Be The Playbook` sections, using a playbook as direct capability proof, or cloning an old phase plan without fresh reasoning is a FAIL.
- **Mechanical check for frontier planning artifacts:** When reviewing a frontier/high-novelty plan or brief and the files exist, run `python scripts/check_playbook_overreach.py --plan <plan_path> [--brief <brief_path>] [--project <project_path>]`. A non-zero result is a FAIL unless the issue is fixed and the checker passes.
- **Campaign / outreach quality:** For lead-gen, outbound, or marketing work, verify target-audience fit, CTA clarity, offer specificity, and compliance requirements for the channel.
- **Missing planning artifact:** If this should have had a creative brief and none exists, treat that as a process failure and do not ship as PASS.

If code is involved, consider using **Codex CLI** for a quality review — it's good at catching bugs and suggesting improvements.

### Step 4a: Enterprise Quality Gate Verification (MANDATORY for all client deliverables)

Read the Enterprise Quality Gate section of [[deliverable-standards]]. For each of the 6 requirements, verify evidence exists and is specific. Use the creative brief's Enterprise Validation Plan as the checklist. **Missing evidence is a FAIL, not a caveat.**

| Gate | What QC Must Verify | FAIL if Missing |
|------|--------------------|-----------------|
| **Ground truth** | Evidence that deliverable output was compared against an independent reference. Must include: reference name, comparison method, delta/match rate. | Yes — "we tested it" without a named reference is not ground truth. |
| **Breadth testing** | Evidence of testing across varied inputs per the deliverable-type minimum in deliverable-standards. Must include: input names/descriptions, pass/fail per input. | Yes — testing against one input is a demo, not validation. |
| **Failure modes** | A "Known Limitations" section exists in the README, deliverable, or delivery handoff. Must answer: what breaks it, what happens when it fails, what edge cases are unhandled. | Yes — no documented limitations means undertested. |
| **Performance** | Profiling results with specific numbers, measurement method, and hardware baseline. Must include scaling data (not just one data point). | Yes for code/CLI, website/web app, data/CSV, dashboard, API/MCP, 3D renders, video, game. For programmatically generated PDFs/documents: generation time and file size required. Waived only for manually authored single-generation documents. Check deliverable-standards for what to profile per type. |
| **Security** | Dependency audit results (zero critical/high), credential handling verification, input sanitization check. | Yes for code/API/MCP/web. Waived for static deliverables (PDF, images, video). |
| **Error recovery** | Evidence of at least one forced failure test (kill mid-operation, bad input, network disconnect) with documented recovery behavior. | Yes for code/CLI, API/MCP, game, dashboard, data/CSV, website/web app. Waived for static deliverables (PDF, images, video). Check deliverable-standards for recovery type per deliverable. |

**If the creative brief has no Enterprise Validation Plan:** this is a process failure. QC verdict is FAIL — Incomplete. Create a ticket to add the validation plan to the brief before re-running QC.

**Evidence location:** Check the QC report, the brief's validation plan, test result files, README/LIMITATIONS.md, the latest credibility-gate report, any `fresh-checkout` / `verify_release.py` outputs, and the delivery ticket work log. If evidence exists but isn't in a client-visible location, flag it for inclusion in the delivery handoff per compliance rule 9.

### Step 4b: Automated Interaction Smoke Testing (MANDATORY for interactive deliverables)

For any deliverable that has user interaction — games, web apps, interactive dashboards, tools with controls, forms, or any UI with buttons/keys/mouse input — you MUST run automated interaction smoke tests before issuing a verdict. Screenshots alone are NOT sufficient. A game can render beautifully and be completely unplayable.

For browser-based or native interactive deliverables, run `python scripts/ensure_qc_walkthrough.py` after the smoke path passes so QC auto-captures `qc-walkthrough.mp4` when the surface is inferable. If the helper cannot capture a required walkthrough and the UI is still genuinely not reviewable in video form, the QC report must explain why.

**Important framing:** This is **smoke testing** — verifying that controls respond at all, not assessing gameplay quality, balance, or feel. Headless browsers with SwiftShader cannot meaningfully evaluate 3D performance or subjective game feel. The goal is: "does pressing W do anything?" not "is the movement speed fun?"

**Tool routing for smoke tests:**
- **Web apps / forms / dashboards:** Use `agent-browser` for navigation, element discovery (snapshot -i), clicking, filling, and screenshots. Faster, token-efficient, and the ref system is ideal for form interaction.
- **Games requiring JS state injection:** Use Playwright Python API for console capture (page.on listeners) and state-before/after comparison (page.evaluate). agent-browser's `eval` is simpler but lacks closure support and event listeners.
- **Hybrid approach (recommended for games):** Use `agent-browser` for initial navigation, screenshots, and simple interactions. Switch to Playwright Python API only for the state injection verification loop.

**Process:**

**Option A: agent-browser path (web apps, forms, dashboards):**
```bash
# Navigate and discover interactive elements
agent-browser --allow-file-access open "file:///path/to/deliverable.html"
agent-browser wait --load networkidle

# Discover all interactive elements
agent-browser snapshot -i
# Output: @e1 button "Submit", @e2 input "Contact", @e3 link "About", ...

# Test each core interaction
agent-browser fill @e2 "test@example.com"
agent-browser click @e1
agent-browser wait --load networkidle
agent-browser screenshot "{deliverables_path}/smoke-after-submit.png"

# Check for errors
agent-browser eval "window.__errors || []"
agent-browser close
```

**Option B: Playwright Python API path (games, state injection):**
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    # Capture console output BEFORE navigation
    console_logs = []
    console_errors = []
    page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
    page.on("pageerror", lambda err: console_errors.append(str(err)))

    # Some apps need HTTP origin — try file:// first
    page.goto("file:///path/to/deliverable.html")
    page.wait_for_timeout(3000)  # let it fully initialize

    # CRITICAL: click the canvas/game area to ensure it has focus
    page.click("canvas", force=True)  # fallback: page.click("body")
    page.wait_for_timeout(500)
```

2. **Extract and classify the control scheme.** Read the deliverable's code to identify every user input. Classify each as:
   - **Core controls** — essential to the deliverable's purpose. MUST work or it's a FAIL.
     - Games: movement, primary attack, camera control, start/play
     - Web apps: primary CTA, form submission, navigation
   - **Secondary controls** — enhance but aren't essential. Issues = REVISE, not FAIL.
     - Games: inventory, map toggle, secondary abilities, pause
     - Web apps: filters, sort, theme toggle, shortcuts

3. **For EACH core control, run a state-based test.** Use JS state injection as the primary verification (more reliable than pixel comparison):

   ```python
   # Read game/app state BEFORE input
   state_before = page.evaluate("""() => {
       try {
           // Adapt these selectors to the specific deliverable
           if (window.game) return JSON.stringify({
               px: window.game.player?.x || window.game.player?.position?.x,
               py: window.game.player?.y || window.game.player?.position?.y,
               pz: window.game.player?.z || window.game.player?.position?.z,
               health: window.game.player?.health,
               camY: window.game.camera?.rotation?.y,
               screen: window.game.currentScreen || window.game.state,
               score: window.game.score
           });
       } catch(e) {}
       return '{}';
   }""")

   # Take screenshot before
   page.screenshot(path="before-W.png")

   # Ensure focus and simulate input
   page.click("canvas", force=True)
   page.keyboard.press("w")
   page.wait_for_timeout(500)

   # Read state AFTER input
   state_after = page.evaluate("...same query...")
   page.screenshot(path="after-W.png")

   # Primary check: JS state changed
   # Fallback check: screenshots differ (but beware ambient animations)
   # Fallback check: DOM elements changed (visibility, classes, text)
   ```

   **If game state isn't accessible via JS:** Fall back to DOM inspection → pixel comparison → note as "unverifiable" and create a human-review ticket.

4. **Test categories:**

   **For games:**
   | Category | Core? | What to test |
   |----------|-------|-------------|
   | Movement | YES | WASD/arrows change player position |
   | Camera | YES | Mouse movement changes view angle |
   | Primary attack | YES | Attack key changes game state (damage, animation) |
   | Start game | YES | Title → gameplay transition works |
   | Abilities | Secondary | Each ability key triggers effect |
   | UI panels | Secondary | Shop/inventory/menu open on click |
   | Pause/resume | Secondary | Pause stops game loop, resume continues |
   | Win/lose | Secondary | Victory/defeat screens trigger |

   **For web apps:**
   | Category | Core? | What to test |
   |----------|-------|-------------|
   | Navigation | YES | Links/routes change page content |
   | Primary CTA | YES | Main button triggers response |
   | Form submit | YES | Valid form data submits successfully |
   | Form validation | YES | Invalid input shows error message |
   | Loading states | Secondary | Async operations show feedback |
   | Responsive | Secondary | Viewport resize doesn't break layout |
   | Text input | Secondary | Typing in fields works |
   | Auth flow | Secondary | Login/logout if applicable |

5. **Console error analysis:**
   ```python
   # Errors were captured by listeners from step 1
   if console_errors:
       print(f"JS ERRORS: {len(console_errors)}")
       for e in console_errors:
           print(f"  - {e[:200]}")
   ```
   Uncaught JS errors during core interactions are a FAIL signal. Warnings are informational only.

6. **Headless limitations — handling what can't be verified:**
   - **3D visual quality** — SwiftShader renders differently than real GPU. Screenshots are evidence but not proof of visual quality.
   - **Performance/FPS** — cannot assess in headless. Note as "not verifiable."
   - **Audio** — check if Web Audio API context exists but can't verify sound plays.
   - **Pointer lock / fullscreen / gamepad** — may not work in headless.
   - For unverifiable items: create a ticket assigned to `human` describing the specific manual test needed. Use verdict **PASS with caveats** if all verifiable tests pass.

7. **Results format.** Include in the QC report as `## Interaction Smoke Test Results`:
   ```
   ## Interaction Smoke Test Results

   **Method:** JS state injection + screenshots + console capture
   **Headless limitations:** 3D visual quality, audio, pointer lock, FPS

   | Control | Type | Input | Verification | Result | Evidence |
   |---------|------|-------|-------------|--------|----------|
   | Move forward | Core | W key | player.z changed | PASS | z: 0 → -2.1 |
   | Attack | Core | Q key | state unchanged | FAIL | no state delta |
   | Camera orbit | Core | Mouse drag | camera.rotation static | FAIL | rotation: 0 → 0 |
   | Shop panel | Secondary | Tab | element visible | PASS | display: none → block |

   **Console errors:** 2 (TypeError line 1204, undefined ref line 890)
   **Manual tests needed:** 3D quality, audio, pointer lock
   ```

8. **Verdict impact:**
   - ANY **core** control dead (no state change on input) → **FAIL — Broken**
   - Only **secondary** controls have issues → **REVISE** (fix tickets, don't block delivery for these alone)
   - All controls work but **console errors** exist → **REVISE** (latent bugs)
   - Tests can't run at all (page won't load, canvas not found) → **FAIL — Broken**
   - All verifiable tests pass, headless limitations prevent full verification → **PASS with caveats** + human-review ticket for manual play-testing

### Step 4c: Stitch Design Comparison (optional, when explicitly applicable)

If the creative brief or ticket indicates Stitch-governed UI work (`design_mode: stitch_required` or `stitch_required: true`) and the brief references Stitch screen IDs under a "Visual Targets" section:

1. For each named Stitch screen (e.g., "ConnectionDialog-empty", "Editor-results"), retrieve the design via `mcp__stitch__get_screen`.
2. Screenshot the built deliverable at the corresponding state/viewport (use agent-browser or Computer Use MCP as appropriate).
3. Use the image-compare MCP to produce a visual diff between the Stitch design and the actual screenshot.
4. Evaluate structural divergence:
   - Layout differences (missing sections, wrong positioning): **REVISE** with diff evidence
   - Color/typography deviations within 10% tolerance: **PASS** (production theming may differ from mockup)
   - Missing entire components visible in the design: **FAIL — Broken**
5. Log comparison results with diff images as evidence in the QC report.
6. For Stitch-governed UI work, the QC report must explicitly reference the Stitch screen IDs or screen names it compared, plus the runtime screenshot filenames used for that comparison. The downstream `check_stitch_gate.py` script reads those references mechanically.
7. If the ticket/brief indicates an existing-surface redesign, verify that `.stitch/DESIGN.md` and the downloaded Stitch artifacts are fresh for this redesign cycle rather than stale leftovers from an older surface. A reused or pre-redesign Stitch artifact is **FAIL — Broken evidence**.
8. The downstream visual gate also consumes concrete screenshot filenames and parity calls mechanically. Vague language like “looks clean” without named screenshots/states is insufficient evidence.

**Hard failure only for explicit Stitch-required UI work:**
If the project/ticket explicitly opts into Stitch-governed frontend design work and the brief does NOT reference Stitch screen IDs, this is **FAIL — Incomplete**, not a fallback scenario. Create a remediation ticket to produce the missing Stitch project, `.stitch/DESIGN.md`, and Visual Targets section before delivery can proceed.

**Legacy fallback only:**
If a project does not explicitly opt into Stitch, skip this Stitch-only step. The UI must still pass the concept, public-surface, page-contract, runtime screenshot, and visual-review gates that apply to the work.

If the work is `design_mode: concept_required`, skip this Stitch-only step and evaluate the public-surface/page-contract/runtime screenshot audits against the concept package instead. If the brief has neither Stitch screens nor another concept source of truth (non-visual project), skip this step entirely.

### Step 4d: Public Surface Design Audit (when applicable)

If the brief or ticket indicates a `public-surface` UI (landing page, homepage, marketing site, pricing page, public first-impression surface):

1. Read the brief's `## Visual Quality Bar` and `## Narrative Structure` sections first. If either required section is missing, this is **FAIL — Incomplete** for public-facing UI work.
2. Evaluate the built page at desktop and mobile viewports against the brief and screenshots:
   - Is there a singular first impression, or does the page read like a pile of features?
   - Is the hierarchy obvious in 2 seconds?
   - Does the page make a product argument, not just enumerate modules?
   - Are there too many boxed cards, repeated panels, or low-value sections diluting focus?
   - Does the CTA feel primary and intentional?
3. Public-facing pages fail if they look generic even when the code is correct. Specifically flag:
   - card soup / over-boxing
   - weak hero proposition
   - no trust/proof layer
   - no “why this beats generic alternatives” layer
   - visually flat or interchangeable SaaS layout
4. If the page is an existing-surface redesign, inspect the desktop above-the-fold screenshot first. If a primary composition anchor from the brief/Stitch target is missing in runtime, this is **FAIL — Broken**, even if the copy, colors, and section ordering improved.
5. The QC report must explicitly state whether the page clears the visual-narrative bar. “Looks clean” is not sufficient evidence.

### Step 4e: Navigation and Page Contract Audit (when applicable)

If the brief or ticket indicates `page-contract-required` (Account, Settings, Billing, Dashboard, Admin, Profile, or other top-level nav surfaces):

1. Read the brief's `## Page Contracts` section. If missing, this is **FAIL — Incomplete**.
2. For each governed page, verify the built surface matches the declared contract:
   - the page serves the expected user job
   - the required sections actually exist
   - empty/loading/error states exist where promised
   - destructive actions live in a clearly labeled danger zone rather than consuming the whole page
3. A top-level nav page that resolves to only one destructive action, one narrow tool, or an obviously incomplete stub is **FAIL — Broken IA** unless the brief explicitly defines that behavior.
4. The QC report must name the page-contract findings explicitly. Do not hide this under generic “UX” notes.

### Step 4f: Operator Console Route-Family Audit (when applicable)

If the brief or ticket indicates `route_family_required` (top-level/internal operator-console surface, primary nav destination, or governed route-family surface):

1. Read the brief's `## Route Family` section first. If missing, this is **FAIL — Incomplete**.
2. Read the brief's `## Composition Anchors` section. If missing, this is **FAIL — Incomplete** for route-family-governed surfaces.
3. Evaluate the built route against both the approved concept and the surrounding product family:
   - Does it feel like the same product family as the approved sibling routes, or like a generic admin template pasted in?
   - Is there one dominant work area with subordinate support zones, or several equal-weight boxes fighting for attention?
   - Did the implementation duplicate page-identity chrome already owned by the app shell?
   - Did filler metric rails, over-boxing, or generic split-panel defaults replace the approved composition?
   - Do the route-level hierarchy, spacing rhythm, and visual density match the family standard named in the brief?
4. Existing-surface redesigns fail if they preserve the old generic layout and merely repaint it with the new tokens.
5. The QC report must explicitly state whether the route clears same-product-family parity. Generic phrases like “looks clean” or “matches tokens” are not enough.
6. Name the concrete runtime screenshots that support that verdict. The downstream visual gate will block delivery if same-product-family parity is asserted without screenshot-level evidence.

### Step 5: Verdict

| Result | Meaning | Action |
|--------|---------|--------|
| **PASS** | All deliverables exist, meet requirements, are production-quality, AND verification protocol fully executed with all steps passing | Proceed to delivery |
| **PASS with caveats** | All deliverables meet requirements but verification protocol has unverifiable steps (documented with human-review tickets created in Step 6) | Proceed to the pre-delivery gate. Caveats must be disclosed to client via gap-communication handoff BEFORE delivery. The credibility gate and final delivery review still run, and the client must acknowledge caveats before the delivery ticket unblocks. Human-review tickets remain open post-delivery. |
| **FAIL — Missing** | One or more promised deliverables don't exist | Create tickets to produce missing items. Do NOT deliver. |
| **FAIL — Broken** | Deliverables exist but are broken, empty, or corrupted (includes build/test failures from Step 2d) | Create tickets to fix. Do NOT deliver. |
| **FAIL — Incomplete** | Deliverables exist but don't fully meet requirements | Create tickets for the gaps. Do NOT deliver. |
| **REVISE** | Deliverables meet requirements but quality is below standard | Create revision tickets with specific notes. Do NOT deliver until QC passes. |

**Hard gate:** A verdict of PASS requires that the Verification Protocol (Step 2d) was executed. If the QC report has no `## Verification Protocol Results` section and the brief defined a protocol, the verdict is automatically FAIL — Incomplete regardless of all other checks.

### Step 6: Create Follow-Up Tickets When Needed

If the verdict is **FAIL**, **REVISE**, or **PASS with caveats**:

1. Create one follow-up ticket per discrete problem using [[create-ticket]].
   - Use the same `project`.
   - If this is client-scoped, pass `client`.
   - Use `priority: high` for missing/broken deliverables and `priority: medium` for revision-quality issues.
2. Do not manually append those tickets to the project. [[create-ticket]] now runs `scripts/ensure_project_ticket_link.py` and is the sole project-task writer. Only repair manually if that helper fails.
3. Update the project status away from `complete`:
   - `active` if the fixes are executable now
   - `blocked` if the missing information is external/human
4. Record the created ticket IDs in the QC report.

### Step 7: Write QC Report

**Determine attempt number** before writing the report:

1. Search the QC report directory (client-scoped or platform-level snapshots) for existing files matching `*qc*{project}*` (this catches `qc-report-`, `qc-phase2-`, `qc-v2-`, `qc-final-`, etc.).
2. Count how many exist. The current report is attempt `count + 1`.
3. If `attempt > 1`, read the most recent prior QC report's verdict and record it as `prior_verdict`.
4. If this is the first QC report for this project, `attempt` is `1` and `prior_verdict` is `~` (null).

Save the report to the resolved QC report path:

```markdown
---
type: snapshot
title: "QC Report — {project}"
project: "{project}"
captured: {now}
agent: quality-check
attempt: {attempt number — 1 for first QC, 2+ for re-checks}
prior_verdict: {verdict from the previous attempt, or ~ if attempt 1}
verdict: "{PASS | PASS with caveats | FAIL — Missing | FAIL — Broken | FAIL — Incomplete | REVISE}"
tags: [qc, deliverables]
---

# QC Report — {project}

## Verdict: {PASS | PASS with caveats | FAIL — Missing | FAIL — Broken | FAIL — Incomplete | REVISE}

## Deliverable Inventory
| File | Exists | Valid | Meets Requirement |
|------|--------|-------|-------------------|
| ... | ... | ... | ... |

## Requirements Checklist
- [x] ...
- [ ] ...

## Brief Compliance
- [[2026-03-17T10:30-creative-brief-T-007-homepage-refresh]] — Palette ✓ | Typography ✓ | Quality bar ✗

## Visual Evidence (MANDATORY for visual deliverables)
| Screenshot | Viewport | Verified |
|------------|----------|----------|
| {filename.png} | {e.g., 1440px desktop} | {PASS/FAIL + notes} |

## Verification Protocol Results
**Protocol source:** {link to creative brief's Verification Protocol section}
**Executed:** {yes/no/partial}

### Build Verification
| Step | Command | Expected | Actual Exit Code | Stderr | Result |
|------|---------|----------|-----------------|--------|--------|
| {step} | {command} | {expected} | {actual} | {excerpt} | {PASS/FAIL} |

### Test Execution
| Suite | Command | Expected | Pass/Fail Counts | Failures | Result |
|-------|---------|----------|-----------------|----------|--------|
| {suite} | {command} | {expected} | {e.g., 142/142} | {none or list} | {PASS/FAIL} |

### Functional Proof
| Proof | Procedure | Expected | Actual | Evidence | Result |
|-------|-----------|----------|--------|----------|--------|
| {proof} | {procedure} | {expected} | {actual} | {path} | {PASS/FAIL} |

### Domain-Specific Verification
| Claim/Element | Method | Expected | Actual | Result |
|---------------|--------|----------|--------|--------|
| {claim} | {method} | {expected} | {actual} | {PASS/FAIL} |

**Protocol Verdict:** {ALL PASS / PARTIAL / FAIL (build) / FAIL (tests) / FAIL (proof) / NOT EXECUTED}

## Quality Notes

**Finding categorization (MANDATORY):** Each finding below must include `[SEVERITY: HIGH|MEDIUM|LOW]` and `[CATEGORY: {category}]` tags from this taxonomy:

`compilation | type-system | wiring/integration | state-isolation | design-quality | test-coverage | documentation | performance | security | verification-evidence | requirements-compliance`

This structured data feeds the [[meta-improvement]] skill for failure chain analysis. If a finding spans two categories, use the primary one (the category that, if fixed, would have prevented the finding).

### Findings
{List each finding with severity and category tags, e.g.:}
{### Finding 1 — Description [SEVERITY: HIGH] [CATEGORY: wiring/integration]}
{Details...}

## Created Tickets
- [[T-00X-fix-missing-deliverable]]
- [[T-00Y-revise-placeholder-copy]]

## Action Required
{if FAIL/REVISE: specific tickets to create or revisions needed}
```

### Step 8: Update Archive Quality Scores

After writing the QC report, update the archive index (`vault/archive/_index.md`) for every capability (MCP or skill) used in this project:

1. For each capability used, find its row in the archive index.
2. Increment **Uses** by 1.
3. If the QC verdict was **PASS** on this attempt, increment **QC Passes** by 1.
4. Update **Last QC** to today's date.
5. Recalculate **Score** = QC Passes / Uses.

This feeds the quality ranking in [[source-capability]] so future projects pick the best-performing capabilities.

## Important

- **Never skip QC to meet a deadline.** Shipping broken work damages trust more than a delay.
- **Never trust a prior agent's claim that something works.** Verify it yourself.
- **If you can't verify something** (e.g., you can't render an image to check it), note that in the report and flag it for human review.

## See Also

- [[test-mcp-server]]
- [[creative-brief]]
- [[self-review]]
- [[gather-context]]
- [[orchestrator]]
- [[create-ticket]]
- [[SCHEMA]]
