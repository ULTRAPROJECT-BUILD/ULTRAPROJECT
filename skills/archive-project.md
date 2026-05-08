---
type: skill
name: archive-project
description: De-identifies completed client projects into reusable playbooks for the archive
inputs:
  - project_path (required — path to the completed project file)
  - client_slug (required — client whose project this is)
---

# Archive Project

You are archiving a completed client project as a de-identified playbook. This runs when a client-facing project reaches a terminal state (complete, blocked with no path, or abandoned).

**Important:** Only archive REAL client-facing projects (under `vault/clients/{slug}/projects/`). NEVER archive:
- Internal/platform projects (under `vault/projects/`) — those would pollute the knowledge base
- Practice client projects (under `vault/clients/practice/projects/`) — fictional work must not become real client playbooks. Check `is_practice: true` in client config before archiving.

## Process

### Step 1: Gather All Project Data

1. Read the project file at `{project_path}`.
2. Read all tickets referenced in the project. Prefer wiki-link targets such as `[[T-001-write-copy]]`, and support legacy bare references such as `[T-001]` if present.
3. Read any decisions in `vault/clients/{client_slug}/decisions/` related to this project.
4. Read any lessons in `vault/clients/{client_slug}/lessons/` related to this project.
5. Read any post-delivery review snapshots in `vault/clients/{client_slug}/snapshots/` related to this project.
6. Identify all MCPs and skills used/built during the project.

### Step 2: Analyze the Project

Extract:
- **Industry** — what business sector (e.g., automotive-services, e-commerce, saas)
- **Business model** — local-service, online-store, subscription, marketplace, etc.
- **Channels** — what platforms/channels were involved (google-ads, email, social, seo, etc.)
- **Project type** — campaign-setup, tool-integration, workflow-automation, etc.
- **Outcome** — success, partial, or failed
- **Duration** — days from project creation to completion
- **Tools used** — list of MCPs and skills
- **Key decisions** — what non-obvious choices were made and why
- **Lessons learned** — what worked, what didn't, what to do differently

### Step 3: De-Identify

Apply these rules strictly:

| Original | De-identified |
|----------|---------------|
| Business name | Generic descriptor: "a car wash business" |
| Owner/contact names | Removed entirely |
| Location | Generalized: "Tampa, FL" → "a mid-size US city" |
| Exact revenue/budget numbers | Ranges: "$4,200/mo" → "$2k-5k/mo range" |
| URLs, emails, phone numbers | Removed |
| API keys, credentials | Already stripped by archive-capability |
| Proprietary product/service names | Generic: "SuperClean Package" → "entry-level service" |
| Specific dates | Relative: "March 2026" → "project duration: 14 days" |

**Preserve:**
- Industry and business model
- Channel strategy and approach
- Campaign/project structure
- Budget ratios and percentages (not absolutes)
- Performance patterns (relative, not absolute)
- What worked and what didn't
- Tools and skills used
- Timeline and sequencing decisions
- Lessons learned (generalized)

### Step 4: Write the Playbook

Create the playbook at `vault/archive/playbooks/{slug}.md`:

```yaml
---
type: archived-playbook
title: "{generalized title, e.g., 'Google Ads setup for a local service business'}"
industry: {industry}
business_model: {business_model}
channels: [{channels}]
project_type: {project_type}
outcome: {success | partial | failed}
duration_days: {duration}
tools_used: [{mcp and skill names}]
skills_used: [{skill names}]
created: {now}
source_client: de-identified
tags: [{relevant tags}]
---

# {title}

## Context
{De-identified description of what the client needed and why.}

## Approach
{Step-by-step strategy that was followed, generalized.}

## What Worked
{Bullet points of successful tactics/decisions.}

## What Didn't Work
{Bullet points of things that failed or underperformed.}

## Key Decisions
{Non-obvious choices made during the project and reasoning.}

## Tools & Skills Used
{List of MCPs and skills, with notes on how they were used.}

## Recommended Approach for Similar Projects
{If doing this again, here's the optimal path — informed by lessons learned.}

## Metrics (Relative)
{Performance indicators in relative terms — percentages, ratios, trends.}
```

### Step 5: Update Playbook Index

1. Read `vault/archive/playbooks/_index.md`.
2. Append the new playbook entry.

### Step 6: Check for Patterns

1. Read all playbooks in `vault/archive/playbooks/`.
2. Find playbooks with matching `industry`, `channels`, or `business_model`.
3. **If 3+ similar playbooks exist and no pattern file covers them:**
   - Create a pattern at `vault/archive/patterns/{slug}.md`:
     ```yaml
     ---
     type: pattern
     title: "{insight, e.g., 'Local service businesses convert best on brand + geo keywords'}"
     confidence: {0.0-1.0, based on consistency across playbooks}
     observed_count: {number of supporting playbooks}
     industries: [{list}]
     business_models: [{list}]
     channels: [{list}]
     created: {now}
     updated: {now}
     source_playbooks:
       - "{playbook-1-slug}.md"
       - "{playbook-2-slug}.md"
       - "{playbook-3-slug}.md"
     tags: [{tags}]
     ---

     # {title}

     ## Observation
     {What the pattern is.}

     ## Evidence
     {Summary of supporting playbooks.}

     ## Recommendation
     {How to apply this pattern to future projects.}
     ```

4. **If a pattern already exists** for this combination:
   - Update `observed_count` and `confidence`.
   - Add this playbook to `source_playbooks`.
   - Update `updated` date.

### Step 7: Confidence Scoring

- 3 playbooks with same outcome: confidence 0.6
- 5 playbooks with same outcome: confidence 0.8
- 8+ playbooks with same outcome: confidence 0.9
- Mixed outcomes reduce confidence by 0.2
- Failed outcomes with consistent failure mode: still a valid (negative) pattern

## Output

Return:
- **Playbook path:** where the de-identified playbook was saved
- **De-identification status:** clean (no PII remaining)
- **Pattern created/updated:** yes/no, pattern name
- **Similar playbooks found:** count

### Step 8: Clean Up Deliverables

After the playbook is archived and the project is complete, clean up large deliverable files that are no longer needed. The client already received them via email — keeping them bloats the vault.

**Only clean files belonging to THIS project.** If the client has other active projects sharing the same `deliverables/` directory, only delete files that were produced by tickets in this project (check ticket work logs for artifact paths). Never delete files from sibling projects.

**Delete:**
- Large data files (`*.csv`, `*.xlsx` over 100KB) produced by this project
- Build artifacts over 100KB (`*.pptx`, generated scripts)
- Redundant screenshots (keep 1 representative screenshot per deliverable for visual reference)

**Keep:**
- One screenshot/thumbnail per visual deliverable (for future reference)
- Creative briefs (in snapshots — small, reusable reference)
- QC reports (in snapshots — quality data for REFLECT)
- Lessons (in lessons/ — feed into consolidation)
- Post-delivery reviews (in snapshots — archive metadata)
- Project file and tickets (small, contain work logs and history)
- The archived playbook itself (in vault/archive/playbooks/)
- README/usage docs and any reusable scripts under 50KB
- HTML deliverables under 100KB (useful as build references for repeat clients)

**How:** Delete individual files by path (from ticket work logs), NOT the entire deliverables directory. Log what was deleted in the project work log: "Cleanup: removed N files ({total size}). Kept: 1 screenshot, briefs, QC reports."

**When:** Only after ALL of: (1) project status is complete, (2) client explicitly accepted delivery (acceptance ticket closed via APPROVE, not timeout), (3) playbook is archived. Never clean up active projects or auto-accepted deliveries.

## What NOT to Archive

- Internal/platform projects (`vault/projects/` — NOT client projects)
- Projects that are still active (wait for terminal state)
- Projects with fewer than 2 completed tickets (not enough substance)

## See Also

- [[match-playbooks]]
- [[orchestrator]]
- [[archive-capability]]
