# Example: Build a Landing Page

A small, end-to-end run that exercises most of the OneShot pipeline — creative brief, design contract, code build, self-review, quality check, polish review, and delivery.

## What this exercises

- `creative-brief` skill — generates a project brief with mission alignment, visual quality bar, and proof strategy
- `project-plan` skill — phases the work and writes tickets
- `code_build` task type — frontend implementation
- `quality_check` skill — runtime evidence (screenshots, accessibility, no-passive-network)
- `artifact-polish-review` — clean-room first-impression review
- `credibility-gate` + `delivery-gate` — evidence-backed handoff
- `vault/` durable memory — the project survives session ends

## Expected scope

- ~5–8 phase tickets
- ~30–90 minutes wall-clock (longer if the visual gates need revisions)
- Output lands in:
  - `vault/projects/landing-page-<your-slug>.md` — project state and orchestrator log
  - `vault/snapshots/<project>/` — brief, plan, review reports, gate artifacts
  - `workspaces/<project>/` — the actual website (HTML/CSS or framework code)
  - `deliverables/<project>/` — final delivery package + screenshots/walkthrough

## Prompt

Copy this block and paste it after `claude -p` or `codex exec`:

```
Read SYSTEM.md and skills/orchestrator.md — especially the Critical Rules block at the top of orchestrator.md, those are load-bearing. Follow the skill literally. Here's what I want to build:

Build a single-page marketing landing page for a fictional product called "Glimmer," a desk lamp that adapts color temperature to your circadian rhythm. The page should:

- have a clear hero (product image placeholder ok), value proposition, three feature highlights, social proof block, FAQ, and CTA
- be a single static HTML/CSS file (no framework required) that I can open in a browser and screenshot
- have a tasteful, modern visual feel — not generic SaaS card-soup
- be fully responsive (375px / 768px / 1440px)
- pass an accessibility quick-check (sufficient contrast, semantic HTML, keyboard reachable)
- ship with QC-stage screenshots (light + dark if applicable, all three breakpoints) plus a short walkthrough video

Run the full quality pipeline (creative brief -> build -> self-review -> QC -> artifact polish review -> delivery). I want a deliverable I'd actually feel comfortable handing to a designer for critique.
```

## Variations

- **Faster run:** drop the dark theme requirement and the walkthrough video; the system will close in fewer cycles.
- **Harder run:** add "must score above 90 on Lighthouse for performance, accessibility, best practices, and SEO." This forces the loop to actually run Lighthouse and iterate.
- **Different domain:** swap "marketing landing page for a desk lamp" with any product or service. The skills are domain-agnostic; the prompt is the only thing that changes.

## What to expect

You'll see the orchestrator:

1. Match the goal against the creative-brief skill, write a brief, gate it.
2. Generate a project plan with named phases.
3. Spawn a `code_build` executor for the page itself.
4. Run `self_review`, `quality_check` (with screenshots), and `artifact_polish_review` against the built page.
5. Run the credibility-gate and final delivery review.
6. Hand off the finished package.

If the page fails any gate, the orchestrator routes a fix ticket and re-runs the affected gate. That's the loop you're paying for.
