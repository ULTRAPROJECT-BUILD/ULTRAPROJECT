---
type: skill
name: post-delivery-review
description: Structured retrospective after project delivery — captures lessons, identifies gaps, and generates improvement actions before archiving
inputs:
  - client (optional — client slug)
  - project (required — project slug)
  - review_path (optional — exact snapshot path; if omitted, use the standard project review path)
---

# Post-Delivery Review

**FIRST-LOOK INSTRUCTION (mandatory before any rubric-based work):** Before reading any spec, manifest, gate report, schema, or running any validation script, use the Read tool to open every rendered PNG / screenshot / mockup image referenced in this review. For this post-delivery review skill, image paths include any PNGs, screenshots, slide renders, runtime captures, or mockups referenced by the delivered artifacts, QC reports, self-review logs, polish reviews, visual gates, and delivery evidence. Look at each image with your own multimodal vision. Write a SHORT, HONEST paragraph (3-6 sentences) titled "First-look gut reaction" describing exactly what you see and how you would react if you were a smart human seeing this for the first time: is it actually beautiful, is it visually thin, does the subject appear, does it have warmth/personality/surprise, does it look like the kind of work the brief promised? Be specific. Be unflattering when warranted. The rubric-based grading that follows MUST explicitly engage with this gut reaction — if your gut says "this looks basic" or "the subject is missing" or "this could be any generic editorial site," the rubric grading must either explain why the work succeeds despite that, or downgrade accordingly. The gut reaction CANNOT be silently ignored. If no rendered PNG / screenshot / mockup image is referenced in this review, state that in the "First-look gut reaction" paragraph and continue. If you cannot open a referenced PNG (paths missing, file unreadable), mark the review REOPEN immediately — no rubric grade is valid without first-look.

**OPERATOR-INTENT CONTEXT (load this BEFORE forming any judgment about alignment, register, or whether the work matches what was promised):** Read the project file for `{project}` — specifically the Context section (which contains the operator's original prompt verbatim or a link to the request snapshot) and the ## Taste / Visual Acceptance Criteria section (which contains active TC-NNN entries that are load-bearing project constraints). Read the project plan for `{project}`. You are not just grading the work against the spec — you are grading whether the work fulfills what the operator ACTUALLY ASKED FOR. The spec is downstream of the prompt; if the spec drifted from the prompt, the work matching the spec is not sufficient. State explicitly: (a) what the operator literally asked for in their prompt, (b) what the spec promised, (c) whether the work matches both — and if there is a gap between (a) and (b), flag it as a brief-spec drift even if the work matches (b).

You just delivered a project. Before archiving it, stop and review the entire engagement. This is where the system learns. Every insight captured here compounds — it feeds into playbooks, patterns, skill improvements, and better creative briefs for future clients.

**Rule: Never archive a project without running post-delivery review first.**

## Process

### Step 0: Determine Scope and Output Path

1. Resolve whether this is:
   - A client-scoped project (`client` provided, or the project lives under `vault/clients/{client}/projects/`)
   - A platform/internal project
2. Resolve the review snapshot path:
   - If `review_path` is provided, use it.
   - If client-scoped: `vault/clients/{client}/snapshots/{project}/{now}-post-delivery-review-{project}.md`
   - If platform-level: `vault/snapshots/{project}/{now}-post-delivery-review-{project}.md`
3. Resolve the lesson directory:
   - Client-scoped: `vault/clients/{client}/lessons/`
   - Platform-level: `vault/lessons/`

### Step 1: Gather the Full Picture

1. Read the project file and all its tickets (open, closed, blocked — all of them).
2. Read the QC report(s) for this project.
3. Read the creative brief(s) if any exist.
4. Read all self-review logs from ticket work logs.
5. Read any decision records related to this project.
6. Count: total tickets, QC failures, revision cycles, escalations.

### Step 2: Assess Delivery vs Requirements

Compare what was delivered against what the client originally asked for:

- **Fully delivered:** requirements met or exceeded
- **Partially delivered:** some requirements met, others missed or compromised
- **Over-delivered:** built things the client didn't ask for (wasted effort?)
- **Under-delivered:** promised things that weren't in the final deliverable

For each gap, note why it happened.

### Step 3: Identify What Went Well

What should the system keep doing? Be specific:
- Which skills worked smoothly?
- Which MCPs performed reliably?
- Where did the creative brief make a real difference?
- What was faster than expected?

**Archive compounding:** The archive is the platform's compound interest. Every successfully delivered project that gets archived as a playbook makes the next similar project faster. Prioritize archiving even for seemingly niche domains — the roguelike game playbook made the MOBA 3x more complex but completable in the same timeframe. When in doubt, archive. (Learned from 2026-03-18-playbook-reuse-compounds-velocity, 2026-03-18)

### Step 3b: Archive Audit

Check whether the project contributed to the platform's reusable archive:

1. List all code written during the project (MCPs, scripts, skills).
2. Check `vault/clients/{client}/mcps/` and `vault/clients/{client}/skills/` — were capabilities built as reusable components?
3. Check `vault/archive/_index.md` — was anything archived?

**If the project wrote code but archived nothing, this is a process failure.** Every project that builds tools should leave reusable capabilities in the archive. Flag it as an improvement action:
- Identify which scripts/code should have been MCPs or skills
- Create tickets to refactor them into proper capabilities and archive them
- This is how the compounding loop works — skip it and the next similar project starts from scratch

### Step 4: Identify What Went Wrong

Honest assessment. Common categories:

- **MCP gaps** — needed a capability that didn't exist or didn't match the domain (e.g., landscape Blender MCP used for a coffee shop)
- **Archive gaps** — code was written as throwaway scripts instead of reusable MCPs/skills; nothing was archived for future reuse
- **QC misses** — things that shipped but shouldn't have (e.g., wrong image, broken page)
- **Self-review blind spots** — what did the agent miss when reviewing its own work?
- **Wasted work** — tickets that had to be redone, false starts, unnecessary iterations
- **Clarification failures** — requirements that were ambiguous and led to wrong output
- **Timing** — things that took too long or blocked the chain unnecessarily

### Step 5: Generate Improvement Actions

For each problem identified, create a concrete action:

| Problem | Action | Type |
|---------|--------|------|
| Blender MCP only has landscape tools | Build domain-specific scene tools per client type, or skip 3D when tools don't match | skill-gap |
| Self-review didn't catch wrong imagery | Add content relevance check to self-review skill | skill-update |
| CSS opacity:0 broke without JS | Add graceful degradation to build-skill quality criteria | skill-update |
| Clarification didn't ask about animation vs stills | Add media format question to the manual client setup checklist | skill-update |

Actions should be one of:
- **skill-update** — improve an existing skill with what was learned
- **skill-gap** — a new skill or MCP capability is needed
- **process-fix** — change in how the orchestrator sequences work
- **lesson** — general insight to record for future reference

### Step 5b: Update Client Preferences

If this is a client-scoped project, update (or create) `vault/clients/{client}/preferences.md` with insights learned from this engagement. This builds a persistent profile so the system works better with this client on future projects.

```markdown
---
type: config
title: "Client Preferences — {client name}"
description: "Persistent preferences and working style for {client name}, built from project history"
updated: {now}
---

# Client Preferences — {client name}

## Communication
- {style: direct/formal/casual, response speed expectations, feedback pattern}

## Work Preferences
- {delivery format preferences: CSV, PDF, website, etc.}
- {project approach: prefers pilots, wants everything at once, iterative}
- {quality expectations: detail-oriented, big-picture, specific formatting needs}

## Successful Approaches
- {what worked well in past projects — e.g., "pilot batch before full scale"}

## Things to Avoid
- {what didn't work or what the client pushed back on}

## Domain Context
- {industry details, tools they use, integrations they need}
```

**Rules:**
- Append to existing preferences, don't overwrite — the file grows with each project.
- Keep observations factual, not judgmental ("prefers detailed progress updates" not "is needy").
- Only capture what's useful for future projects — skip one-off details.
- If the file already exists, update the `updated` date and add new insights under the relevant sections.

### Step 6: Decide Whether the Project Can Stay Complete

Classify the review:

- **PASS** — delivery matched the client's actual requirements; only lessons/process improvements were found
- **REOPEN — Remediation Required** — the project was under-delivered, materially wrong, or should not have been considered complete

Use **REOPEN — Remediation Required** when any of the following are true:
- A delivered artifact does not match the client's business or request
- A promised requirement was missed or only partially delivered
- The wrong deliverable was shipped, even if a file technically existed
- The project needs another client-facing correction cycle

If the verdict is **REOPEN — Remediation Required**:
1. Create one remediation ticket per discrete issue using [[create-ticket]].
2. Use the same `project`, and pass `client` when scoped.
3. Do not manually append the remediation tickets to the project. [[create-ticket]] now owns project task-list updates via `scripts/ensure_project_ticket_link.py`.
4. Update the project status away from `complete`:
   - `active` if the remediation work can proceed now
   - `blocked` if outside input or approval is required
5. Record the remediation ticket IDs in the review.
6. Do **not** archive the project yet.

### Step 7: Write Lessons

For each significant insight, create a lesson file in the appropriate directory:
- Client-scoped: `vault/clients/{client}/lessons/`
- Platform-level: `vault/lessons/`

Use the lesson schema from [[SCHEMA]]. Tag lessons with the relevant skills so [[consolidate-lessons]] can route them correctly.

### Step 8: Write the Review

Save the review to the resolved `review_path`:

```markdown
---
type: snapshot
title: "Post-Delivery Review — {project}"
project: "{project}"
captured: {now}
agent: post-delivery-review
tags: [review, retrospective, lessons]
---

# Post-Delivery Review — {project}

## Verdict: {PASS | REOPEN — Remediation Required}

## Summary
- **Client:** {name or "platform"}
- **Delivered:** {date}
- **Tickets:** {total} total, {closed} closed, {qc_failures} QC failures, {revision_cycles} revision cycles

## Delivery vs Requirements
| Requirement | Status | Notes |
|-------------|--------|-------|
| ... | Delivered / Partial / Missed | ... |

## What Went Well
- ...

## What Went Wrong
- ...

## Improvement Actions
| Problem | Action | Type | Priority |
|---------|--------|------|----------|
| ... | ... | ... | ... |

## Lessons Created
- [[2026-03-17-lesson-slug]]
- ...

## Remediation Tickets
- [[T-00X-fix-delivered-mismatch]]
- ...
```

## Principles

- **Be brutally honest.** The review is internal — nobody sees it but the system and the admin. Sugarcoating problems means they repeat.
- **Be specific.** "Quality could be better" is useless. "The hero image was from a different industry because the Blender MCP lacked coffee shop scene tools" is actionable. Lessons must be concrete enough to drive measurable changes in the next project — "improve quality" produces nothing; "use Three.js for 3D instead of silently downgrading to 2D" produces a measurably better V2. (Learned from 2026-03-18-v2-rebuild-validates-lesson-driven-improvement, 2026-03-18)
- **Focus on systemic fixes.** One-off mistakes don't need process changes. Repeated patterns do.
- **Every problem needs an action.** If you identify a problem but don't propose a fix, the review is incomplete.
- **Do not let a bad delivery hide behind a retrospective.** If the review finds material under-delivery, reopen the project with remediation tickets instead of archiving it.

## Archive Feedback

If the review flags issues caused by a specific capability (MCP or skill), add a note to that capability's entry in `vault/archive/_index.md` describing the issue. For example: "stock-data MCP returned stale prices during market hours — consider adding a cache-busting parameter." This helps future agents make informed sourcing decisions.

## See Also

- [[create-ticket]]
- [[consolidate-lessons]]
- [[archive-project]]
- [[quality-check]]
- [[self-review]]
- [[orchestrator]]
- [[SCHEMA]]
