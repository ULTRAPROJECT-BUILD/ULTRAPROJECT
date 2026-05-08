# Example: Research and Report

A research-driven run that produces a written deliverable backed by cited evidence. Exercises the creative-brief, mission-alignment audit, evidence-grounded writing, and review pipeline — without producing code.

## What this exercises

- `creative-brief` skill — for non-code work, the brief defines acceptance criteria, evaluator lens, and proof strategy
- `project-plan` skill — phases the research and writing
- WebSearch / WebFetch usage — agents pull real sources
- `quality_check` — claim/evidence parity, citation completeness, scope fidelity
- `artifact-polish-review` — clean-room first-impression review of the written report
- Mission-alignment audit — every claimed conclusion traces to the original goal

## Expected scope

- ~5–7 phase tickets
- ~30–60 minutes wall-clock
- Output lands in:
  - `vault/projects/<slug>.md` — project state
  - `vault/snapshots/<project>/` — brief, plan, source notes, review reports
  - `deliverables/<project>/` — the report itself + a citation manifest

## Prompt

```
Read SYSTEM.md and skills/orchestrator.md — especially the Critical Rules block at the top of orchestrator.md, those are load-bearing. Follow the skill literally. Here's what I want to build:

Produce a 6-8 page primer titled "What changed about agent harnesses in 2025?" The reader is a technical decision-maker who already knows what an LLM is but has not been tracking the agent-tooling space closely.

The primer should:

- cover at least four meaningful shifts (e.g., model-context-protocol adoption, code-execution sandboxing, tool selection at scale, evaluation methodology)
- cite real, verifiable sources (papers, blog posts, repos, talks). Every non-trivial claim needs a citation.
- include a one-page "what to bet on, what to ignore" closer with the author's own opinion clearly labeled as opinion
- be written cleanly — no bullet-soup, no marketing tone
- ship as a single Markdown file plus a separate citation manifest with every URL accessed

Run the full quality pipeline (creative brief -> research -> draft -> self-review -> QC -> artifact polish review -> delivery). The final artifact should survive a clean-room reviewer who has not seen the build process.
```

## Variations

- **Different topic:** swap the title and reader profile. The skills are domain-agnostic.
- **Heavier rigor:** add "must include a comparison table, a glossary, and a numbered references section." This forces the writing executor to produce more structured output.
- **Faster run:** drop the citation-manifest deliverable and the closer page; the loop closes in fewer cycles.

## What to expect

You'll see the orchestrator:

1. Run the creative-brief skill and gate it against the rigor tier.
2. Plan research → outline → draft → self-review → QC → polish.
3. Spawn a research executor that uses WebSearch and WebFetch (these must be available in your tool config).
4. Spawn a writing executor that produces the report.
5. Run `quality_check` for claim/evidence parity — every cited URL must be reachable, every claim must trace to a source.
6. Run `artifact_polish_review` clean-room against just the report (no work logs) to judge whether it lands.
7. Hand off the package.

If a gate fails — typically claim-without-citation or scope drift from the brief — the orchestrator routes a fix and re-runs. That's the loop catching scope drift before the reader does.
