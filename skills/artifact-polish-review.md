---
type: skill
name: artifact-polish-review
description: Clean-room review of the finished artifact pack after QC. Focuses on first impression, finish, trust, and whether the deliverable feels intentionally reviewed by a human.
inputs:
  - project (optional)
  - ticket_id (required)
  - client (optional)
  - deliverables_path (required)
  - creative_brief_path (required)
  - creative_brief_paths (optional — ordered applicable brief stack: project -> phase -> ticket)
  - qc_report_path (optional)
  - review_pack_json (optional)
  - review_pack_markdown (optional)
---

# Artifact Polish Review

This is the clean-room consumption review layer. It happens **after QC** and asks a different question:

- QC asks: does the deliverable meet the spec and proof requirements?
- Artifact polish review asks: does the actual artifact feel finished, credible, intentional, and human-reviewed?

You are not the builder here. Do not start by reading code, work logs, or self-justification. Start from the artifact pack.

## Process

### Step 1: Build or load the review pack

If a review pack was not provided, build it first:

```bash
python3 scripts/build_review_pack.py \
  --deliverables-root "{deliverables_path}" \
  --brief "{creative_brief_path}" \
  {qc_report_args_if_available} \
  --json-out "{snapshots_path}/{date}-review-pack-{project}.json" \
  --markdown-out "{snapshots_path}/{date}-review-pack-{project}.md"
```

The review pack is the artifact manifest. It is the starting point for this review.

If the review pack marks walkthrough video as `required` for the artifact type, treat a missing walkthrough artifact as a real review defect. Do not silently continue as if screenshots cover the same ground.

### Step 2: First-impression pass

Before reading builder notes, inspect the artifact pack itself:

- landing page / website screenshots
- walkthrough videos / screen recordings when present
- rendered documents / PDFs / slides
- media stills / clips
- data outputs / rendered charts / sample rows
- packaged app surfaces / screenshots / README / handoff

Write down what feels true in the first 10 seconds.

Questions:

- Does this feel credible immediately?
- What feels unfinished, generic, thin, awkward, or confusing?
- If this is a revision, did it actually fix the thing that was rejected?

### Step 3: Deep artifact pass

Read [[deliverable-standards]] and review the artifact against the universal polish rubric:

- If `creative_brief_paths` is provided, read the full ordered brief stack first.
- Otherwise treat `creative_brief_path` as the governing base brief and look for any active phase-scoped supplement before judging the artifact.
- Resolution order is: project brief -> phase brief -> ticket brief. More specific briefs narrow or override the broader brief on conflict.

- First Impression
- Coherence
- Specificity
- Friction
- Edge Finish
- Trust
- Delta Quality (when this is a revision)

Important rules:

- Do not reward a deliverable for technical correctness alone.
- A deliverable can pass QC and still fail polish review.
- Do not confuse “clean” with “finished.”
- Prefer 3-7 high-signal findings over a huge laundry list.
- If the structure itself is weak, say so directly instead of suggesting micro-polish.

### Step 4: Verdict

Use one of:

- `PASS`
  - Artifact feels finished, intentional, and defensible under human review.
  - Grade must be `A` band.
- `REVISE`
  - Artifact is functional but still has meaningful polish/trust/finish defects.
- `FAIL`
  - Artifact is materially below bar, misleading, or clearly not review-ready.

### Step 5: Write the report

Save a markdown snapshot with frontmatter like:

```markdown
---
type: snapshot
title: "Artifact Polish Review — {project}"
project: "{project}"
ticket: "{ticket_id}"
captured: {now}
agent: artifact-polish-review
grade: "A"
verdict: "PASS"
tags: [polish, review, clean-room]
---
```

Required sections:

- `## Verdict: {PASS | REVISE | FAIL}`
- `## Grade: {A-F}`
- `## Top Findings`
- `## First Impression`
- `## Coherence`
- `## Specificity`
- `## Friction`
- `## Edge Finish`
- `## Trust`
- `## Delta Quality` (required for revisions, otherwise state `N/A`)

The report must cite concrete artifact evidence:

- screenshot filenames
- walkthrough video filenames
- document/page names
- file paths from the review pack
- specific visible/user-facing issues
- if walkthrough video was required by the review pack, whether it was present and whether it materially helped the review

Do not hide behind vague phrases like “could be more polished.” Name what is actually off.
