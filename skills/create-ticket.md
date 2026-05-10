---
type: skill
name: create-ticket
description: Creates a new ticket in the vault ticket system (supports client-scoped tickets)
inputs:
  - title (required)
  - project (required — project slug)
  - status (optional — default: open. Valid values: open, waiting, blocked)
  - priority (optional — default: medium)
  - task_type (optional — default: general)
  - complexity (optional — default: standard. Valid values: standard, deep. "deep" enables multi-pass execution with checkpointing)
  - phase (optional — numeric phase number when the ticket belongs to a planned phase)
  - wave (optional — active/planned wave name when the ticket belongs to a capability-wave campaign)
  - remediation_for (optional — parent ticket ID when this ticket is remediation or follow-up work)
  - assignee (optional — default: agent)
  - due (optional)
  - blocked_by (optional — list of ticket IDs)
  - tags (optional)
  - ui_work (optional — default: false. True when the ticket materially changes a user-facing UI surface)
  - design_mode (optional — default: "". Canonical UI contract when `ui_work: true`: `stitch_required`, `concept_required`, or `implementation_only`)
  - stitch_required (optional — default: false. Mechanical Stitch gate flag. True only when `design_mode` is explicitly `stitch_required`)
  - public_surface (optional — default: false. True for landing pages, pricing pages, marketing pages, or other public-facing surfaces that must clear the visual-narrative bar)
  - existing_surface_redesign (optional — default: false. True when the ticket is redesigning an already-existing user-facing surface and must first establish a greenfield concept)
  - page_contract_required (optional — default: false. True for account/settings/dashboard/admin or other top-level nav surfaces that must have a non-destructive information architecture)
  - route_family_required (optional — default: false. True for top-level/internal operator-console surfaces that must match an approved route family instead of drifting into generic admin layouts)
  - delivery_surface_type (optional — for delivery / re-delivery tickets: github_repo, web_url, platform_distribution, download_link, attachment_bundle)
  - delivery_surface_ref (optional — repo slug, URL, or platform build identifier)
  - delivery_surface_access_subject (optional — GitHub username or platform account that should have access)
  - delivery_surface_verified (optional — default: false)
  - delivery_surface_verified_at (optional)
  - body (required — description of the work)
  - client (optional — client slug; when provided, creates ticket in vault/clients/{client}/tickets/)
---

# Create Ticket

## Instructions

`task_type` should be intentional, not a shrug. In addition to the existing core task types:
- Use `code_build` for code implementation/modification work.
- Use `code_review` for standard code-review / fix-finding work. Premium gate and delivery reviews may still explicitly force Codex when the orchestrator calls them.
- Use `visual_review` for the orchestrator-owned screenshot/design-fidelity gate on governed UI work. This is the authoritative Claude visual verdict step, not a generic implementation ticket.
- Use `artifact_cleanup` for bounded non-code artifact refresh/consistency cleanup.
- Use `receipt_cleanup` for JSON receipt / machine-readable evidence cleanup.
- Use `docs_cleanup` for README/docs truth-alignment and wording-only documentation cleanup.
- Use `general` for bounded non-gate work that does not fit a narrower task type. High-judgment planning/control-plane work should use its specific task types instead of hiding inside `general`.

0. **Determine ticket location:**
   - If `client` is provided: use `vault/clients/{client}/tickets/` as the ticket directory and `vault/clients/{client}/tickets/.counter` as the counter file.
   - If `client` is NOT provided: use `vault/tickets/` and `vault/tickets/.counter` (platform-level).

1. **Validate the ticket counter** at the determined counter path before using it.
   - If the file is missing or contains anything other than a whole number, treat it as corrupted.
   - Recover by scanning the **determined ticket directory** (not always `vault/tickets/` — use the client-scoped directory if `client` is provided) for the highest `T-xxx` ID number in existing ticket filenames.
   - Recreate `.counter` with that highest numeric value.
   - If no tickets exist, recreate `.counter` with `0`.
   - If recovery cannot determine a single highest ID because ticket filenames are malformed or conflicting, stop and return an explicit counter corruption error instead of guessing.
2. **Read the ticket counter** at the determined counter path to get the current count.
3. **Increment the counter** by 1 and write it back to that `.counter`.
4. **Generate the ticket ID**: `T-` followed by the counter zero-padded to 3 digits (e.g., `T-001`).
5. **Create the ticket file** at the determined ticket directory as `{id}-{slug}.md` where `{slug}` is a kebab-case version of the title (max 5 words).
6. Resolve `{now}` from the machine-local clock at write time (for example, `date +"%Y-%m-%dT%H:%M"` on macOS/Linux/WSL, `Get-Date -Format "yyyy-MM-ddTHH:mm"` in PowerShell, or an equivalent local Python datetime command). Do not guess or convert from UTC unless the source value explicitly includes a timezone.
7. **Write the file** with this template:

```markdown
---
type: ticket
id: {id}
title: "{title}"
status: {status}
priority: {priority}
task_type: {task_type or general}
project: "{project}"
assignee: {assignee}
created: {now}
updated: {now}
due: {due or ""}
blocked_by: {blocked_by or []}
complexity: {complexity}
phase: {phase or ""}
wave: "{wave or ''}"
remediation_for: "{remediation_for or ''}"
tags: {tags or []}
ui_work: {ui_work or false}
design_mode: "{design_mode or ''}"
stitch_required: {stitch_required or false}
public_surface: {public_surface or false}
existing_surface_redesign: {existing_surface_redesign or false}
page_contract_required: {page_contract_required or false}
route_family_required: {route_family_required or false}
delivery_surface_type: {delivery_surface_type or ""}
delivery_surface_ref: "{delivery_surface_ref or ''}"
delivery_surface_access_subject: "{delivery_surface_access_subject or ''}"
delivery_surface_verified: {delivery_surface_verified or false}
delivery_surface_verified_at: "{delivery_surface_verified_at or ''}"
---

# {title}

{body}

## Work Log

- {now}: Ticket created
```

8. **Add a project back-link** in the ticket body after the H1 using the literal sentence `Part of project [[{project-slug}]].`
9. **Append the canonical project task link** by running:
   - `python scripts/ensure_project_ticket_link.py --ticket-path "{ticket_path}"`
   This step is mandatory. `create-ticket` is the sole project-task writer. Do not rely on downstream skills to manually append the ticket to the project's `## Tasks` section.
10. **UI contract:** If the ticket creates or materially redesigns a user-facing UI surface (landing page, dashboard, web app screen, mobile screen, admin panel, visual refresh), set:
   - `ui_work: true`
   - `design_mode` to one of: `stitch_required`, `concept_required`, or `implementation_only`
   - tags including `ui-design`
   - `stitch_required: true` and tag `stitch-required` only when the operator/project explicitly opts into Stitch and `design_mode: stitch_required`
   Frontend design work must not skip design intent. The runtime reads these fields and will enforce the appropriate UI contract mechanically.
11. **Design-mode selection rule:** Choose `design_mode` deliberately:
   - `concept_required` by default for public surfaces, existing-surface redesigns, rejected visual work, and high-ambiguity/high-drift multi-screen UI that still needs a real concept, visual direction, and screenshot-driven QC
   - `stitch_required` only when the operator explicitly asks for Stitch or the project intentionally makes Stitch the visual source of truth
   - `implementation_only` only for low-risk polish or follow-through on an already-approved design/source of truth
   If a UI ticket cannot honestly be called implementation-only, do not use that mode.
12. **Public-surface rule:** If the ticket governs a landing page, homepage, pricing page, marketing site, or other public-facing surface where first impression matters, also set:
   - `public_surface: true`
   - tags including `public-surface`
   These tickets must clear a stronger visual/narrative bar than ordinary product UI.
13. **Existing-surface redesign rule:** If the ticket is redesigning an already-existing user-facing surface inside an existing app/site, also set:
   - `existing_surface_redesign: true`
   - tags including `existing-surface-redesign`
   Existing-surface redesigns must not treat the current DOM/layout as the design source of truth. The brief and downstream review work must force a greenfield concept pass, plus explicit `Composition Anchors` and `Replace vs Preserve` sections before implementation.
14. **Page-contract rule:** If the ticket governs a top-level nav surface such as `Account`, `Settings`, `Billing`, `Dashboard`, `Admin`, or another page users reasonably expect to contain multiple sections/states, also set:
   - `page_contract_required: true`
   - tags including `page-contract-required`
   A top-level nav destination must not collapse to a single destructive action or one narrow sub-feature unless the brief explicitly says so.
15. **Route-family rule:** If the ticket governs a top-level internal/operator-console surface such as `Pending Review`, `Handoff`, `Memory Browser`, `Trust Ledger`, `Audit Timeline`, `Live Watch`, `Agent Console`, `Retrieval / Context`, `Knowledge Graph`, or another primary navigation destination where product-family consistency matters, also set:
   - `route_family_required: true`
   - tags including `route-family-required`
   These surfaces must inherit an approved route family instead of improvising a generic admin split-panel/card stack. The brief and QC must make same-product-family parity explicit.
16. **UI review inheritance rule:** If you create self-review, QC, or artifact-polish-review tickets that govern the same UI surface as a build/redesign ticket, copy the same UI metadata onto those review tickets:
   - `ui_work`
   - `design_mode`
   - `stitch_required`
   - `public_surface`
   - `existing_surface_redesign`
   - `page_contract_required`
   - `route_family_required`
   Review tickets without the governing UI metadata are structurally incomplete because the runtime and gates will relax at exactly the point they should be strictest.
17. **Delivery-surface rule:** For delivery and re-delivery tickets, set the canonical review surface in frontmatter:
   - `delivery_surface_type`
   - `delivery_surface_ref`
   - `delivery_surface_access_subject` when private access must be verified
   This tells the system where the client is actually supposed to review the work. A delivery ticket without a review surface is incomplete.
18. **Reopen the project if needed** — read the project file at the correct path:
   - If `client` is provided: `vault/clients/{client}/projects/{project}.md`
   - If no client: `vault/projects/{project}.md`

   If the project's `status` is `complete`, reopen it:
   - Set to `active` if the new ticket is `open` (work can proceed)
   - Set to `blocked` if the new ticket is `waiting` or `blocked` (work can't proceed yet)

   A complete project with open tickets will be skipped by the next orchestration pass.
19. **Phase/wave inheritance rule:** When creating remediation, follow-up, or gate-fix tickets inside an existing project:
   - copy the current project phase number into `phase`
   - copy the active wave name into `wave` when the project uses `execution_model: capability-waves`
   - set `remediation_for` to the failed or blocking parent ticket ID when applicable
   These fields are not optional in practice for project-managed remediation work. They keep the per-project `status.md`, wave log, and downstream review stack honest.
20. **Return** the ticket ID and file path.

## Error Handling

- If `vault/tickets/.counter` is corrupted, never increment it in place. Run the recovery flow in Step 0 first.
- If Step 0 fails because the ticket directory contains ambiguous or malformed IDs, stop and surface the corruption error for manual repair.

## Atomicity

- Ticket creation must be atomic around the counter. If creating multiple tickets, create them sequentially and never in parallel.
- If the counter changes unexpectedly during a run, restart from Step 0 before creating the next ticket.

## Client-Scoped Tickets

When the `client` parameter is provided:
- Tickets are created in `vault/clients/{client}/tickets/` using that client's own `.counter` file.
- The counter validation, recovery, and atomicity rules apply identically to client-scoped counters.
- The ticket ID format remains `T-xxx` — IDs are unique within each namespace (platform or client) but may overlap across namespaces.
- When referencing client-scoped tickets elsewhere, prefix with the client slug for clarity: `{client}/T-001`.

## Example

Input:
- title: "Write launch announcement copy"
- project: "q2-campaign"
- priority: high
- body: "Draft 3 variants of the launch announcement. Include subject lines."

Output:
- Created `vault/tickets/T-001-write-launch-announcement-copy.md`
- Ticket ID: T-001

## See Also

- [[SCHEMA]]
- [[check-tickets]]
- [[create-project]]
- [[orchestrator]]
