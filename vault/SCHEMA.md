# Vault Schema

Every markdown record in the vault uses YAML frontmatter for metadata. This allows agents to query by status, type, assignee, tags, and dates.

Auxiliary non-markdown files may also exist in the vault for system bookkeeping, such as `vault/tickets/.counter`, and do not use frontmatter.

## Frontmatter Fields

Temporal metadata fields should use ISO 8601 datetime format: `YYYY-MM-DDTHH:MM` (e.g., `2026-03-17T10:30`). Generate these values from the machine-local clock at write time (for example, `date +"%Y-%m-%dT%H:%M"` in the current system timezone). Do not infer them from memory, and do not write UTC or another timezone as a naive local timestamp. This applies to fields such as `created`, `updated`, `completed`, `decided`, `learned`, `captured`, `tos_accepted_date`, and `payment_requested_date`. Calendar-only fields such as `due` and legal `effective_date` may remain `YYYY-MM-DD`. Legacy date-only records may remain until they are next updated.

### Projects (`vault/projects/` or `vault/clients/{slug}/projects/`)
```yaml
---
type: project
title: "Project name"
status: planning | active | paused | blocked | complete
goal: "One-line goal statement"
created: YYYY-MM-DDTHH:MM
updated: YYYY-MM-DDTHH:MM
due: YYYY-MM-DD | "" (optional)
owner: orchestrator | human
has_existing_codebase: true | false (optional — default: false. Set to true when the project modifies or extends an existing codebase. Triggers Phase 0 indexing via Refactor Engine and graph-backed code context in sync-context.)
target_codebase_path: "{absolute path to codebase}" (optional — required when has_existing_codebase is true. The absolute path to the codebase root that Refactor Engine should index.)
tags: []
---
```

### Tickets (`vault/tickets/` or `vault/clients/{slug}/tickets/`)
```yaml
---
type: ticket
id: T-001
title: "Ticket title"
status: open | in-progress | blocked | waiting | closed
priority: low | medium | high | critical
task_type: general | creative_brief | self_review | quality_check | visual_review | artifact_polish_review | delivery | email_composition | vault_navigation | onboarding | code_build | code_review | code_fix | test_generation | verification_manifest_generate | verification_manifest_execute | test_manifest_generate | test_manifest_execute | mcp_build | mcp_review | orchestration | inbox_processor | artifact_cleanup | receipt_cleanup | docs_cleanup | data_enrichment | research | reflect | reflection | source | archive | study | writing | creative | practice | execution | build | capability-sourcing | skill_build | knowledge-management | data_generation | scout | review | game_dev | environment_setup | integration_test | setup (optional — default: general. `verification_manifest_*` is the canonical proof-oriented naming; `test_manifest_*` remains as a legacy-compatible alias.)
project: "project-slug"
assignee: agent | human
created: YYYY-MM-DDTHH:MM
updated: YYYY-MM-DDTHH:MM
completed: YYYY-MM-DDTHH:MM | "" (optional — only when work is actually completed)
due: YYYY-MM-DD | "" (optional)
blocked_by: [] (list of ticket IDs)
complexity: standard | deep (optional — default: standard. "deep" enables multi-pass execution with checkpointing via deep-execute skill)
file_paths: [] (optional — list of file paths relative to target_codebase_path that this ticket will read or modify. Used by sync-context to assemble graph-backed code context for existing-codebase projects. Only applicable when the project has has_existing_codebase: true.)
ui_work: true | false (optional — default: false. True when the ticket materially changes a user-facing UI surface.)
design_mode: stitch_required | concept_required | implementation_only | "" (optional — default: "". Canonical UI design contract when `ui_work: true`. `stitch_required` = high-ambiguity or high-drift visual work that must use Stitch MCP. `concept_required` = user-facing design work that must define a concept/visual direction but does not require Stitch. `implementation_only` = low-risk follow-through on an already-approved design/source of truth.)
stitch_required: true | false (optional — default: false. Backward-compatible mechanical flag for Stitch-governed work. Set true when `design_mode: stitch_required` or when the UI work must use Stitch MCP as the design source of truth.)
public_surface: true | false (optional — default: false. True for landing pages, marketing pages, pricing pages, and other client/public-facing surfaces that must clear a visual-narrative bar.)
existing_surface_redesign: true | false (optional — default: false. True when the ticket is redesigning an already-existing user-facing surface and must break free of the current layout before implementation.)
page_contract_required: true | false (optional — default: false. True when the ticket governs a top-level navigational page or settings/account/dashboard surface that must have a non-destructive information architecture.)
delivery_surface_type: github_repo | web_url | platform_distribution | download_link | attachment_bundle | "" (optional — strongly recommended for delivery / re-delivery tickets. Describes where the client can review the deliverable right now.)
delivery_surface_ref: "org-or-user/repo-name" | "https://..." | "platform build/channel identifier" | "" (optional — required when delivery_surface_type is set)
delivery_surface_access_subject: "github-username-or-platform-account" | "" (optional — who should have access when the surface is private)
delivery_surface_verified: true | false (optional — default: false. True only after the executor verifies the review surface is updated and accessible)
delivery_surface_verified_at: YYYY-MM-DDTHH:MM | "" (optional — only when delivery_surface_verified is true)
tags: []
---
```

### Project Task Lists

Project files should keep ticket references inside `## Tasks` using the canonical format:

```markdown
- [ ] [[T-001-ticket-slug|T-001]]: Ticket title
```

- Use `[x]` when the referenced ticket is already closed/complete at the moment the line is written.
- `[[create-ticket]]` is the sole project-task writer and should enforce this via `scripts/ensure_project_ticket_link.py`.
- Legacy bare `T-001:` lines may remain until backfilled, but new entries should use the canonical wiki-linked format.

### Skills (`skills/`)
```yaml
---
type: skill
name: create-ticket
description: Creates a new ticket in the vault ticket system
inputs:
  - title (required)
  - project (required — project slug)
  - priority (optional — default: medium)
---
```

### Decisions (`vault/decisions/`)
```yaml
---
type: decision
title: "What was decided"
project: "project-slug" (optional)
decided: YYYY-MM-DDTHH:MM
decided_by: agent | human
tags: []
---
```

### Lessons (`vault/lessons/`)
```yaml
---
type: lesson
title: "What was learned"
project: "project-slug" (optional)
learned: YYYY-MM-DDTHH:MM
tags: []
---
```

### Playbooks (`vault/playbooks/` — reusable workflow instructions)
```yaml
---
type: playbook
title: "Playbook name"
description: "When to use this"
tags: []
---
```

### Config (`vault/config/`)
```yaml
---
type: config
title: "Config name"
description: "What this config controls"
updated: YYYY-MM-DDTHH:MM
---
```

### Log (`vault/config/*-log.md`, including `admin-log.md`, `spending-log.md`, `outreach-log.md`)
```yaml
---
type: log
title: "Log name"
description: "What this log records"
updated: YYYY-MM-DDTHH:MM
---
```

### Registry (`vault/clients/_registry.md`)
```yaml
---
type: registry
title: "Client Registry"
description: "Master list of all clients"
updated: YYYY-MM-DDTHH:MM
---
```

### Legal (`vault/config/legal/`)
```yaml
---
type: legal
title: "Document name"
version: "1.0"
status: "TEMPLATE - REQUIRES ATTORNEY REVIEW BEFORE USE" (optional)
effective_date: YYYY-MM-DD | "[EFFECTIVE DATE]" (optional)
updated: YYYY-MM-DDTHH:MM
---
```

### Index (`vault/archive/_index.md`, `vault/archive/playbooks/_index.md`)
```yaml
---
type: index
title: "Index name"
description: "What this index catalogs"
updated: YYYY-MM-DDTHH:MM
---
```

### Client Config (`vault/clients/{slug}/config.md`)
```yaml
---
type: client-config
slug: "client-slug"
name: "Client Name"
email: "client@example.com"
domain: "industry or 'unknown'"
status: onboarding | active | paused | churned | suspended | deleted
created: YYYY-MM-DDTHH:MM
updated: YYYY-MM-DDTHH:MM
tos_accepted: true | false
tos_accepted_date: YYYY-MM-DDTHH:MM | ""
tos_version: "1.0" | ""
payment_status: pending | paid | active | overdue | churned
admin_override: true | false (optional — bypass payment gate only when explicitly authorized)
payment_method: stripe | crypto | ""
payment_amount_usd: 0
payment_requested_date: YYYY-MM-DDTHH:MM | ""
payment_type: onboarding | monthly | custom | ""
budget_cap_usd: 50.00
is_practice: false (optional — true only for the internal practice client. Skips email/delivery, prevents archiving to playbooks, runs at platform priority)
notes: "Brief summary of client needs"
---
```

### Archived Playbooks (`vault/archive/playbooks/`)
```yaml
---
type: archived-playbook
title: "Google Ads setup for a local service business"
industry: automotive-services
business_model: local-service
channels: [google-ads]
project_type: campaign-setup
outcome: success | partial | failed
duration_days: 14
tools_used: [google-ads-mcp, browser-mcp]
skills_used: [build-mcp-server, create-ticket]
created: YYYY-MM-DDTHH:MM
source_client: de-identified
tags: [google-ads, local, service-business]
---
```

### Patterns (`vault/archive/patterns/`)
```yaml
---
type: pattern
title: "Local service businesses convert best on brand + geo keywords"
confidence: 0.0-1.0
observed_count: 3
industries: [automotive-services, hvac, plumbing]
business_models: [local-service]
channels: [google-ads]
created: YYYY-MM-DDTHH:MM
updated: YYYY-MM-DDTHH:MM
source_playbooks:
  - "playbook-slug-1.md"
  - "playbook-slug-2.md"
tags: [google-ads, local, pattern]
---
```

### Snapshots (`vault/snapshots/`)

**Directory layout (project-grouped):**

```
vault/snapshots/
├── _platform/                          # platform-level snapshots (no specific project)
│   └── 2026-04-27T1108-vault-status.md
├── incoming/                           # operator inbox (system slot — not grouped)
└── <project-slug>/                     # one folder per project
    ├── 2026-04-27T1142-project-plan.md
    ├── 2026-04-27T1150-creative-brief.md
    └── ...
```

For client-scoped projects, the same grouping applies under the client root:

```
vault/clients/<client>/snapshots/
├── incoming/
└── <project-slug>/
    └── 2026-04-27T1142-project-plan.md
```

The folder is the project slug (matches the `project:` frontmatter field). Filenames keep their existing `<NOW>-<artifact>-<project>.md` convention so cross-project search by filename pattern still works.

**Frontmatter:**

```yaml
---
type: snapshot
title: "Snapshot description"
project: "project-slug" (optional — required for project-grouped snapshots; omit for `_platform/`)
ticket: "T-001" (optional — when the snapshot is tied to a specific ticket)
captured: YYYY-MM-DDTHH:MM
agent: "agent identifier"
tags: []
---
```

### Project Derived Context (`vault/projects/<slug>.derived/`)

Each project has five derived/regenerable artifacts that the platform's helper scripts produce alongside the canonical project file. To keep the projects directory visually clean, these live in a `<slug>.derived/` sibling folder rather than next to the project markdown:

```
vault/projects/
├── <slug>.md                          # canonical, human-edited project file
└── <slug>.derived/                    # regenerated by scripts; safe to wipe and rebuild
    ├── current-context.md             # human/agent-readable "what matters now"
    ├── artifact-index.yaml            # machine-readable authoritative pointers
    ├── status.md                      # sleek at-a-glance status (Obsidian/GH preview friendly)
    ├── image-evidence-index.yaml      # screenshots / QC slides / walkthrough frames index
    └── video-evidence-index.yaml      # walkthrough video index
```

For client-scoped projects, the same layout applies under the client root:

```
vault/clients/<client>/projects/
├── <slug>.md
└── <slug>.derived/
    └── ...
```

**Rules:**

- The `<slug>.md` file is the canonical truth. Everything in `<slug>.derived/` is regenerable — wipe and rebuild from `scripts/build_project_context.py`, `scripts/build_project_image_evidence.py`, `scripts/build_project_video_evidence.py` at any time.
- Helper scripts auto-create `<slug>.derived/` on first write (`parent.mkdir(parents=True, exist_ok=True)`).
- Do not edit files in `<slug>.derived/` by hand — they will be overwritten on the next refresh. If you find yourself wanting to, that means the source-of-truth (`<slug>.md`, the project plan, or the underlying snapshots) needs the change instead.

### Project Plan Snapshots (subtype of snapshot)
```yaml
---
type: snapshot
subtype: project-plan
title: "Project Plan — {project title}"
project: "project-slug"
client: "client-slug or _platform"
current_phase: 1
total_phases: 4
captured: YYYY-MM-DDTHH:MM
agent: project-plan
tags: [plan, architecture]
---
```

**Note:** Project plans are **living documents** — they are updated in place as phases advance, unlike regular snapshots which are point-in-time captures. The `captured` date is the creation date; `current_phase` reflects the latest state. Contains Architecture Decisions (binding), Phase breakdown, Artifact Manifest, and Open Questions.

### Project Amendment Snapshots (subtype of snapshot)
```yaml
---
type: snapshot
subtype: project-amendment
title: "Project Amendment — {project title}"
project: "project-slug"
client: "client-slug or _platform"
captured: YYYY-MM-DDTHH:MM
status: pending
classification: phase_amendment # minor_ticket_delta | phase_amendment | project_replan | pivot
apply_mode: phase_brief_delta    # direct_ticket_delta | phase_brief_delta | project_rebaseline | pivot_replace
requires_phase_brief_update: true
requires_project_replan: false
requires_ticket_reblock: true
pause_current_execution: false
request_summary: "Short human-readable summary of the requested change"
source_kind: email
source_subject: "Optional source summary"
source_message_id: "<message-id>" # optional
---
```

**Note:** Project amendment snapshots are the structured record for mid-project change control. They do not replace the project plan or briefs; they explain whether the new request should become a direct ticket delta, a phase-brief amendment, a project rebaseline, or a pivot.

## Work Log Format

Work logs should use a Markdown H2 section named `## Work Log` followed by timestamped bullet entries using `YYYY-MM-DDTHH:MM` format:

```markdown
## Work Log

- 2026-03-16T14:30: Ticket created
- 2026-03-17T09:15: Client approval received
```

## Configuration Schemas

### `inbox_sources`

Used in project files or global config to tell the inbox processor what to monitor:

```yaml
inbox_sources:
  email:
    check: true
    mcp: email
    filters: ["from:client@example.com", "subject:Q2 Campaign"]
  slack:
    check: true
    mcp: slack  # not yet implemented — placeholder
    channels: ["#project-q2", "#client-approvals"]
  webhooks:
    check: true
    watch_dir: vault/snapshots/incoming/
```

## Naming Convention

Files are named with kebab-case slugs:
- Projects: `q2-campaign-launch.md`
- Tickets: `T-001-write-email-copy.md`
- Decisions: `2026-03-16-chose-sendgrid.md`
- Lessons: `2026-03-16-api-rate-limits.md`
- Playbooks: `send-client-email.md`
- Snapshots: `2026-03-16-campaign-metrics.md`

## Querying

Agents find relevant files by:
1. Globbing the directory (e.g., `vault/tickets/*.md`)
2. Reading frontmatter to filter by status, project, assignee, etc.
3. Using grep to search content

## Wiki Links

All non-data vault files use Obsidian `[[wiki links]]` to connect related content in the graph.

### Convention

- **No links in frontmatter** — YAML fields stay as plain strings so agents can parse programmatically.
- **Body text** uses `[[basename]]` for inline references to other vault files (e.g., `[[orchestrator]]`, `[[platform]]`).
- **Every relational file** has a `## See Also` section at the bottom with a bulleted list of related files.
- **Shortest basename** — use `[[file-name]]` not `[[path/to/file-name]]`.

### Patterns by File Type

**Skills:**
```markdown
Use [[create-ticket]] to open a new ticket.

## See Also
- [[orchestrator]]
- [[create-project]]
```

**Tickets:**
```markdown
Part of project [[demo-test-run]].

## See Also
- [[demo-test-run]]
```

**Projects:**
```markdown
- [ ] Verify vault structure [[T-001-verify-vault-structure]]

## See Also
- [[SCHEMA]]
- [[orchestrator]]
```

**Legal docs:**
```markdown
See [[privacy-policy]] for data handling details.

## See Also
- [[terms-of-service]]
- [[ai-disclosure]]
```

### What Does NOT Get Links

- Frontmatter fields (YAML)
- Append-only logs (`admin-log.md`, `spending-log.md`)
- Data tables (`_registry.md`)
- Shell scripts, Python files, JSON configs
- Content inside fenced code blocks

## See Also

- [[SYSTEM]]
- [[CLAUDE]]
- [[create-ticket]]
- [[create-project]]
- [[build-skill]]
