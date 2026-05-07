---
type: skill
name: match-playbooks
description: Searches the archive for playbooks and patterns matching a client's needs during onboarding/planning
inputs:
  - industry (optional — client's industry)
  - business_model (optional — client's business model)
  - channels (optional — list of channels/platforms relevant to the project)
  - project_type (optional — type of project being planned)
  - keywords (optional — additional search terms)
  - frontier_project (optional — true when the project is novel, high-risk, platform-level, extreme-scale, or otherwise not a routine repetition)
  - reuse_mode_cap (optional — one of pattern_only, component_reuse, template_allowed; defaults to pattern_only when omitted)
---

# Match Playbooks

You are searching the archive for prior art — playbooks and patterns from previous projects that can inform the current plan. This runs during onboarding and project planning.

## Process

### Step 1: Search Playbooks

1. Read `vault/archive/playbooks/_index.md` for the catalog.
2. Glob all files in `vault/archive/playbooks/*.md` (excluding `_index.md`).
3. Read the frontmatter of each playbook.
4. Score each playbook against the search criteria:

**Scoring:**
| Match | Points |
|-------|--------|
| Exact industry match | +3 |
| Same business_model | +3 |
| Overlapping channel (any) | +2 per channel |
| Same project_type | +2 |
| Keyword match in title/tags | +1 per match |
| Outcome = success | +1 bonus |
| Outcome = failed | -1 (but still include — knowing what failed is valuable) |

5. Rank playbooks by score. Include any with score >= 3.
6. After Step 1b classification, re-rank: **Full reference** playbooks get +3 bonus, **Structure only** get +0, **Cautionary** get -2. This ensures the "Best match" in the briefing is actually the best quality reference, not just the closest topic match.

### Step 1b: Evaluate Playbook Quality Against Current Standards

For each matching playbook, assess whether its approach and outputs would meet TODAY's standards — not just whether the topic matches.

1. Read the playbook body (not just frontmatter). Look at:
   - What was actually delivered (deliverable descriptions, tools used, approach)
   - What the outcome was and any noted issues
   - When it was created (older = more likely outdated)

2. Compare against current [[deliverable-standards]] and the system's current capabilities:
   - Would the deliverables described in this playbook pass today's QC?
   - Were quality skills used (creative brief, self-review, runtime verification)?
   - Were capabilities archived properly?

3. Classify each playbook's usefulness. **Important:** this is a quality classification, not automatic permission to copy the old architecture. Reuse permission is handled separately by the safe reuse mode.

   | Classification | Meaning | How to use it |
   |---------------|---------|---------------|
   | **Full reference** | Approach AND quality would pass today's standards | Use for project structure, creative direction, and quality benchmarking |
   | **Structure only** | Project sequencing and capability list are useful, but output quality is below current bar | Use for ticket planning and capability sourcing. Ignore as a quality reference. Explicitly note: "Do NOT use this playbook's output quality as the target — it predates current QC standards." |
   | **Cautionary** | The project had significant issues (QC failures, client complaints, missing deliverables) | Reference only for what NOT to do. Include the lessons learned, not the approach. |

4. Also assign a **safe reuse mode** for each playbook:

   | Safe Reuse Mode | Meaning | Allowed inheritance |
   |-----------------|---------|---------------------|
   | **pattern_only** | Most conservative. Use for lessons, risks, process shape, and anti-patterns only. | No architecture proof, no scale proof, no product shape cloning, no phase-plan copying without fresh justification. |
   | **component_reuse** | Specific modules, checklists, scripts, or proven subflows may be reused with fresh project-specific rationale. | Components and bounded workflows only. Core architecture still requires first-principles reasoning. |
   | **template_allowed** | The project is sufficiently repetitive that the old structure can serve as a starting template. | Structure may be reused, but client-specific or scale-specific claims must still be re-proven. |

5. Default conservatively:
   - If `frontier_project: true`, cap every match at **pattern_only** unless the caller explicitly states otherwise.
   - If `reuse_mode_cap` is omitted, default to **pattern_only**.
   - **Cautionary** playbooks are always **pattern_only**.
   - **Structure only** playbooks are **pattern_only** unless there is a clearly bounded component worth reusing.
   - **Full reference** playbooks default to **component_reuse**, not `template_allowed`.
   - `template_allowed` is only appropriate for low-novelty repeatable work where the deliverable shape, channel, and operational constraints are materially the same.

6. Include both the quality classification and safe reuse mode in the briefing so the orchestrator and creative brief know how to use each playbook.

### Step 2: Search Patterns

1. Glob all files in `vault/archive/patterns/*.md`.
2. Read the frontmatter of each pattern.
3. Match patterns where:
   - Industry overlaps
   - Business model overlaps
   - Channels overlap
4. Rank by `confidence` score.

### Step 3: Build Briefing

Generate a briefing document:

```markdown
## Prior Art Briefing

**Search criteria:** industry={industry}, model={business_model}, channels={channels}

### Matching Playbooks ({count} found)

**Best match: {playbook title}** (score: {score}, quality: {Full reference | Structure only | Cautionary}, reuse: {pattern_only | component_reuse | template_allowed})
- Industry: {industry}, Model: {model}
- Outcome: {success/partial/failed}
- Duration: {days} days
- Key insight: {1-sentence summary of the most important takeaway}
- Tools used: {list}
- **Quality note:** {why this classification — e.g., "Created before QC/self-review existed. Use for project structure only." or "Passed QC with 0 revision cycles. Full reference."}
- **Reuse note:** {what can be inherited safely and what must be re-proven from scratch}

**Also relevant:**
- {playbook title} — {1-sentence summary} (score: {score}, quality: {Full reference | Structure only | Cautionary}, reuse: {pattern_only | component_reuse | template_allowed})
- {playbook title} — {1-sentence summary} (score: {score}, quality: {Full reference | Structure only | Cautionary}, reuse: {pattern_only | component_reuse | template_allowed})

### Matching Patterns ({count} found)

**{pattern title}** (confidence: {score}, observed: {count} times)
- {recommendation from the pattern}

### Recommended Approach

Based on prior art:
1. {First recommended step, informed by playbook without exceeding the reuse cap}
2. {Second recommended step}
3. {Watchouts from failed/partial playbooks}

### Tools to Reuse

From matching playbooks, these tools are already in the archive:
- {mcp/skill name} — {what it does} (archive path: {path})
```

### Step 4: Return Results

Return:
- The briefing document (markdown)
- List of matching playbook paths (for the caller to read in detail if needed)
- List of matching pattern paths
- List of reusable tools from the archive
- Whether prior art was found (true/false)

## When No Matches Found

If no playbooks or patterns match:
1. Return an empty briefing: "No prior art found for this combination."
2. This is normal for the first client in a new domain.
3. After this project completes, [[archive-project]] will create the first playbook.

## Usage Context

This skill is called by:
- **Manual client setup** — during client setup, to inform the project plan
- **[[orchestrator]]** — during Phase 1 (Assess), before breaking a goal into tasks
- **Any agent** doing project planning — to check if similar work has been done before

## The Compounding Effect

```
0 playbooks → "No prior art. Building from scratch."
1 playbook  → "Found 1 reference. Use it as bounded prior art."
3 playbooks → "Pattern emerging. Stronger priors available, but still verify novelty and reuse limits."
8 playbooks → "Well-established operating memory. Planning is faster, but frontier work still needs first-principles origination."
```

## See Also

- [[archive-project]]
- [[orchestrator]]
- [[source-capability]]
