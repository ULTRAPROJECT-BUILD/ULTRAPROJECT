---
type: skill
name: self-review
description: Reviews output before final delivery or before closing a dedicated review ticket — catches mediocrity, missing details, and craft issues that functional QC misses
inputs:
  - project (optional — project slug when reviewing a full delivery set)
  - ticket_id (required — the ticket being worked on)
  - client (optional — client slug)
  - deliverables_path (optional — where output files are)
  - creative_brief_path (optional — the creative brief to review against)
  - creative_brief_paths (optional — ordered applicable brief stack: project -> phase -> ticket)
  - review_scope (optional — project or ticket; default: infer from context)
---

# Self-Review

You are reviewing work before delivery. This may happen inline on a build ticket or as a dedicated project-level self-review ticket. This is where mediocre becomes professional. The goal is to catch everything that a client would notice but a functional test wouldn't.

**Rule: Every client-facing deliverable set must pass self-review before delivery.** This may happen inline on the build ticket or through a standalone `Self-review` ticket.

**Important:** Self-review is builder-side review. It is not a substitute for the later clean-room `artifact_polish_review` gate, which looks at the finished artifact with fresh eyes and minimal build context.

## Process

### Step 0: Resolve Scope

1. Read the ticket and project first.
2. Determine review mode:
   - If `review_scope` is provided, use it.
   - If the current ticket is a dedicated review ticket covering multiple deliverables, treat it as **project-level** review.
   - Otherwise default to **ticket-level** review.
3. Resolve the creative brief:
   - If `creative_brief_paths` is provided, use that ordered stack first.
   - Otherwise if `creative_brief_path` is provided, use it as the governing base brief.
   - For **project-level** review, prefer a project-scoped creative brief for `{project}` (matching `project` with no ticket-scoped override). If one does not exist, fall back to ticket-scoped briefs for the execution tickets being reviewed.
   - If a phase-scoped creative brief exists for the current phase, treat it as a supplement to the project brief rather than a replacement.
   - For **ticket-level** review, prefer a ticket-scoped brief for `ticket: {ticket_id}` and fall back to the project-scoped brief if that is what governs the whole project.
   - Resolution order is: project brief -> phase brief -> ticket brief. More specific briefs narrow or override the broader contract on conflict.
   - If no applicable brief exists, stop treating this as shippable work. Create or request the brief first.
4. Resolve the artifact set under review:
   - Ticket-level review: the artifacts produced by that ticket.
   - Project-level review: the full deliverable set referenced by the execution tickets, project notes, and `deliverables_path`.

### Step 1: Step Back

1. Stop building. Read the original requirements and creative brief again with fresh eyes.
2. Read [[deliverable-standards]] for the relevant deliverable type. These are the baseline professional standards that apply automatically — the brief sets the bar higher, never lower.
   - If multiple applicable briefs exist, read the whole stack before judging. The project brief defines the master contract; phase and ticket briefs define local deltas.
3. Ask yourself honestly: "If I were paying for this, would I be impressed? Or would I think 'this looks like AI made it'?"
4. If you don't have a creative brief, flag this — the work should not have started without one.

### Step 2: Artifact Review (use the paths that apply)

**Websites / local HTML / rendered communication HTML:**

Take a screenshot using `agent-browser` (default — Playwright MCP has been removed, `agent-browser` replaces it):

```bash
agent-browser --allow-file-access open "file://{path_to_html}"
agent-browser wait --load networkidle
agent-browser scroll down 99999
agent-browser wait 1000
agent-browser scroll up 99999
agent-browser wait 500
agent-browser screenshot "{deliverables_path}/self-review-screenshot.png" --full
agent-browser close
```

Fall back to Playwright Python API only if you need JS-disabled comparison or console error capture (see [[quality-check]] Step 1b for routing rules).

**Games (Godot, UE5, any engine):**

- **Launch the game and play it.** Do NOT just check code structure or run headless tests. You must visually verify the game looks and plays like a finished product.
- Screenshot the main menu, each encounter/area, and any UI screens. For each: are textures applied? Is lighting active? Are models final assets or graybox? Are VFX visible?
- Test every core mechanic: move, shoot, take damage, die, restart. If any is broken, verdict is Restart.
- Verify audio is playing: weapon sounds, footsteps, music, UI sounds. Silence is a bug.
- Check for graybox: if ANY visible surface is untextured placeholder geometry, this is not shippable. The assets may exist in the project but not be wired into the level — that's an integration failure, not a missing asset.
- Play from start to finish. Can you complete the game? Any softlocks? Does it end properly?
- Ask yourself: "Would a player who downloaded this feel like they got a finished game or a tech demo?" If tech demo → Revise or Restart.
- (Learned from 2026-03-20: FPS game had 19 models, 43 audio files, VFX scenes, and shaders but shipped as a graybox because self-review only checked code and headless tests.)

**Images / renders:**

- Verify dimensions, file size, and format.
- Open or inspect the actual image and review composition, lighting, cropping, texture quality, and whether the result looks intentional rather than placeholder-like.
- If there are multiple images, compare them as a set for consistency.

**Video / animation:**

- Check duration, resolution, codec, and file size.
- Extract representative still frames or a contact sheet and inspect motion quality, framing, transitions, and whether the video feels polished rather than auto-generated filler.
- Verify the asset works in its intended context (hero loop, embed, download, etc.).

**Copy / marketing content / communication drafts:**
*(Note: client-facing communication drafts should be professionally formatted and include required disclosure language when applicable.)*

- Read the entire piece out loud.
- Check subject lines, opening hook, CTA clarity, specificity to the client, and whether the tone matches the brief.
- Reject anything that sounds like generic AI filler or a first draft.

**Documents / PDFs / slides (PPTX, PDF, etc.):**

- **Visual rendering (mandatory for PPTX):** You MUST convert slides to images and visually inspect each one. Do NOT rely on programmatic checks alone — z-order bugs, overlapping shapes, and text overflow are invisible without rendering. Run:
  ```bash
  # LibreOffice exposes 'soffice' on macOS, 'libreoffice' on Linux
  which libreoffice || which soffice || brew install --cask libreoffice
  which pdftoppm || brew install poppler

  # Derive PDF filename from PPTX path (e.g., my-deck.pptx → my-deck.pdf)
  PPTX_PATH='{pptx_path}'
  PDF_NAME="$(basename "$PPTX_PATH" .pptx).pdf"
  libreoffice --headless --convert-to pdf --outdir /tmp/ "$PPTX_PATH" \
    || soffice --headless --convert-to pdf --outdir /tmp/ "$PPTX_PATH"

  # Convert PDF to per-slide PNGs (pdftoppm is mandatory — sips only renders one page)
  mkdir -p '{deliverables_path}/self-review-slides'
  pdftoppm -png -r 200 "/tmp/$PDF_NAME" '{deliverables_path}/self-review-slides/slide'
  ```
  **Verify slide count:** Confirm the number of generated PNGs matches the PPTX slide count. If not, the conversion is incomplete.
  Then **read each slide image** and check:
  - No shapes or rectangles overlapping text (z-order issues are the #1 python-pptx bug)
  - No text cut off at slide edges (overflow)
  - Sufficient contrast — text readable on all backgrounds
  - Layout looks intentional, not broken or auto-generated
  - Brand styling is visible and correct
- Inspect page hierarchy, spacing, typography, and whether pages feel complete and presentation-ready.
- Verify exported assets render cleanly and are not clipped, blurry, or obviously template-driven.
- (Learned from 2026-03-19: AI Executive Presentation had shapes covering text on 2 slides — self-review passed 17/17 programmatic checks but never rendered the slides to look at them. Visual rendering is mandatory.)

For any visual review, evaluate:

**Layout & Spacing:**
- Is there enough whitespace? (Most AI output is too dense)
- Is the visual hierarchy clear? (Can you tell what's most important in 2 seconds?)
- Are sections visually distinct or does it all blur together?

**Typography:**
- Are fonts consistent? (Not mixing 4 different styles)
- Is text readable? (Not too small, not too light)
- Do headings have clear hierarchy? (H1 > H2 > H3 should be visually obvious)

**Color:**
- Does the palette feel cohesive? (Not random colors)
- Is there enough contrast for readability?
- Does it match the creative brief's direction?

**Imagery:**
- Do images look professional or obviously AI-generated/low-quality?
- Are they sized appropriately? (Not stretched, not tiny)
- Do they support the content or just fill space?
- **Content relevance:** Does every image depict the client's actual business/industry? A landscape render on a coffee shop site is wrong even if it's technically a valid image. (Learned from 2026-03-17-wrong-blender-scene-reused, 2026-03-17)

**Overall Impression:**
- Does this look like a real business's website? Or a homework assignment?
- Would a client show this to their friends proudly?
- What's the ONE thing that looks most amateur? Fix that.

### Step 2.5: Verification Protocol Quick-Check

If the creative brief defines a `## Verification Protocol` section, run the **Regression Anchor** subset before proceeding to content review. This is not the full protocol execution (that happens in quality-check Step 2d) — this is a fast build-and-smoke check to catch obvious breakage before spending time on visual/content polish.

1. Read the creative brief's Verification Protocol section.
2. If no protocol section exists:
   - For code/software deliverables with a new brief (created on or after 2026-03-23): flag as brief deficiency in Step 5.
   - For code/software deliverables with a legacy brief (created before 2026-03-23): use the Runtime Acceptance Test section as the verification method. Additionally attempt best-effort build/test based on the project's build system (`npm test`, `cargo test`, etc.). Log results.
   - For static deliverables (HTML, PDF, images): skip — covered by Step 2 artifact review (visual screenshots, structure checks).
   - For knowledge deliverables: skip automated check — note for human review.
3. If a protocol exists, run every command listed in the **Regression Anchor** subsection:
   - Build Verification commands: run each, verify exit code 0.
   - Test Execution subset: run specified suites, verify pass.
   - Functional Proof subset: run specified proof, verify expected result.
4. If all pass: proceed to Step 3. Save evidence as a snapshot (`{date}-phase-{N}-verification-evidence.md`) with: each command run, exit code, output excerpt (first 20 lines of stderr if any), and pass/fail. Note "Verification Protocol quick-check: PASS" in the review log.
5. If any fail: verdict is **Revise** (test failures in non-critical paths) or **Restart** (build doesn't compile). Save evidence snapshot with failure details. Fix the issues before spending time on visual polish — there is no point polishing a deliverable that doesn't build.

**Why this exists in self-review:** Self-review happens during or immediately after the build ticket. Catching a broken build HERE means the builder fixes it in the same context. Waiting for QC (potentially cycles later, after context is lost) is more expensive.

### Step 3: Content Review

Read all copy in the deliverable:

- **Headlines:** Are they compelling or generic? "Welcome to Our Website" is generic. "Example City's Most Trusted Landscaping Team" is specific.
- **Body text:** Is it specific to this client or could it be any business? Replace every generic sentence with something specific.
- **CTA:** Is it clear what the visitor should do? Is the CTA visible and compelling?
- **Details:** Are there placeholder texts, Lorem ipsum, [BRACKETS], or TODO comments? These are automatic failures.

### Step 4: Technical Review

- **Responsive:** Does it work at mobile widths? Take a 375px screenshot too. Also test at exact breakpoint boundaries (767px AND 768px, 1023px AND 1024px) — off-by-one breakpoint bugs are common and only appear at the boundary, not at representative widths. (Learned from shly-nonprofit website-redesign post-delivery-review, 2026-03-18)
- **Performance:** Are images optimized? (No 5MB PNGs for thumbnails)
- **Graceful degradation:** Does the page work without JavaScript? Take a JS-disabled screenshot and compare — content hidden behind `max-height: 0`, `opacity: 0`, or `display: none` that relies on JS to reveal is a failure. **Exception:** JS-heavy web apps (React, Vue, dashboards, games-in-browser) inherently require JS — skip this check for those. (Learned from shly-nonprofit website-redesign post-delivery-review, 2026-03-18)
- **Links:** Do all internal links work? Do anchor links scroll correctly?
- **Asset integrity:** Do files open, render, and package correctly in the form the client will actually receive?

### Step 5: Brief Compliance

Check the applicable brief for this review scope:

- Color palette matches? ✓/✗
- Typography matches? ✓/✗
- Quality bar met? ✓/✗
- Anti-patterns avoided? ✓/✗
- References reflected in the work? ✓/✗
- For non-visual work: deliverable contract met? ✓/✗, structure correct? ✓/✗, proof standard met? ✓/✗, failure modes avoided? ✓/✗
- Verification Protocol defined? ✓/✗ (if no protocol exists for a code/software deliverable, flag as brief deficiency)
- Verification Protocol Regression Anchor passed? ✓/✗/N/A

### Step 5.5: Visual Evidence Ownership Check

For user-visible UI work, do not blur the line between what this review owns and what an upstream/downstream stage owns.

- **Upstream-owned visual evidence must already exist.** If the brief, media contract, Stitch design stage, or build ticket says benchmark/design screenshots should have been produced earlier, verify the files exist and cite their filenames. Missing upstream-owned visual artifacts are a **Revise** verdict, not a note to “maybe capture later.”
- **QC-owned runtime capture is separate.** Runtime screenshots and walkthrough videos are normally QC-owned artifacts unless the brief explicitly assigns them to self-review. If they are QC-owned and not yet produced, note the absence honestly, but do not pretend they exist or cite vague evidence.
- **If you rely on any screenshot as evidence, cite the actual filename.** “Reviewed the screen visually” is not evidence.

### Step 6: Decide

| Verdict | Action |
|---------|--------|
| **Ship it** | The work meets the brief's quality bar, [[deliverable-standards]] for its type, AND the Verification Protocol's Regression Anchor passes (if defined). If the protocol's regression anchor was not executed and a protocol exists, this verdict cannot be used — run Step 2.5 first. For visual/UI work, any upstream-owned benchmark/design screenshots or other required visual artifacts must already exist before this verdict can be used. If this is a dedicated self-review ticket, close the review ticket and record that delivery may proceed. If this is inline review on a build ticket, close the build ticket. |
| **Revise** | Specific issues found. If this is inline review, fix them now and re-run self-review. If this is a standalone self-review ticket, create or reopen fix tickets, keep the review ticket open/blocked on them, and re-run after the fixes land. |
| **Restart** | The output is fundamentally below the quality bar. The approach is wrong, not just the details. Go back to the creative brief and rethink. If this is a standalone review ticket, route the rework back into execution tickets rather than pretending review itself can fix it. |
| **Escalate** | After 3 serious passes, the work still does not meet the bar. Keep the current review ticket open/blocked, create a human-review ticket, and stop pretending it is done. |

**Maximum 3 revision cycles.** If you can't get it right in 3 passes:
- Do **not** close the current ticket.
- Set the current ticket to `blocked`.
- Create a follow-up ticket assigned to `human` (or another explicit reviewer) with the self-review notes and what is still wrong.
- Do not manually append that new human-review ticket to the project. [[create-ticket]] now owns project task-list updates via `scripts/ensure_project_ticket_link.py`.

### Step 7: Log the Review

Append to the ticket's work log:

```
- {now}: Self-review completed. Verdict: {Ship it | Revise (pass N) | Restart | Escalate}.
  Notes: {what was checked, what was fixed, what's still not ideal}
```

## Common Failure Modes

These are the things AI-generated output gets wrong most often. Check for ALL of them:

1. **Too generic** — copy reads like it could be any business. Fix: add specific details about THIS client.
2. **Too dense** — not enough whitespace. Fix: increase padding, reduce content per section.
3. **Inconsistent styling** — some sections look polished, others look rushed. Fix: apply the same level of care everywhere.
4. **Placeholder content** — "Lorem ipsum," "[Your text here]," stock photos. Fix: replace everything with real content.
5. **No visual hierarchy** — everything looks the same importance. Fix: make the primary message 3x larger than secondary.
6. **Default framework look** — looks like Bootstrap/Tailwind out of the box. Fix: customize colors, fonts, spacing, components.
7. **Low-quality assets** — blurry images, obviously AI-generated graphics, tiny icons. Fix: higher resolution, better quality, or different approach.

## See Also

- [[creative-brief]]
- [[quality-check]]
- [[orchestrator]]
- [[gather-context]]
