---
type: skill
name: project-change-control
description: Handle mid-project change requests safely by creating a structured amendment artifact, classifying impact, and deciding whether to add tickets, amend the phase brief, replan, or pivot.
inputs:
  - project (required — project slug)
  - project_file (required — path to the project markdown file)
  - change_request (required — the new requested change text)
  - source_kind (optional — email, admin, note; default email)
  - source_subject (optional — source email subject or short summary)
  - source_message_id (optional — source reference id)
---

# Project Change Control

Use this when new work lands **during an active project** and does not fit cleanly into either:
- a normal ticket update, or
- a post-delivery revision cycle.

The goal is to keep the system flexible **without** letting scope mutate informally underneath the plan, briefs, and gates.

## Process

### Step 1: Read the current project truth

Read:
- the project file
- the latest `current-context.md`
- the latest `artifact-index.yaml`
- the active phase brief / project brief

Understand:
- what phase the project is in
- what tickets are active or blocked
- what the current review/gate surface is
- whether the new request changes mission, phase scope, or just the ticket graph

### Step 2: Create an amendment artifact

Run:

```bash
python3 scripts/create_project_amendment.py \
  --project-file "{project_file}" \
  --request-text "{change_request}" \
  --source-kind "{source_kind}" \
  --source-subject "{source_subject}" \
  --source-message-id "{source_message_id}"
```

This creates a `project-amendment` snapshot and updates the project's `## Pending Amendments` section.

### Step 3: Respect the classification

The amendment artifact will classify the request into one of four buckets:

1. `minor_ticket_delta`
- Bounded follow-up inside the existing plan.
- Action: create scoped ticket(s), link the amendment artifact, refresh context.

2. `phase_amendment`
- The current phase scope or proof needs to change, but the project mission still holds.
- Action: amend/update the phase brief first, then create the execution ticket(s). Re-check whether downstream review tickets should remain blocked until the amendment lands.

3. `project_replan`
- The new request changes architecture, workstreams, proof shape, or phase map enough that the project plan is now stale.
- Action: stop expanding downstream work, create a replan/rebaseline ticket or re-run planning, then re-block affected downstream tickets until the new plan is accepted.
- Routing: use `task_type: project_replan` for the replan/rebaseline ticket so deterministic plan reconciliation runs on Codex. Reserve `task_type: orchestration` for live control-plane decision loops.

4. `pivot`
- The new request effectively replaces the current goal.
- Action: pause the current project, create the replacement project, and do not smuggle the new mission in as “just another ticket.”

### Step 4: Keep the quality pipeline honest

- Do **not** bypass self-review, QC, artifact polish, or delivery gates just because the amendment arrived mid-project.
- If the amendment changes acceptance criteria, proof expectations, or visual targets, update the governing brief/plan layer before spawning execution.
- If the amendment is just a small bounded fix, ticket-level handling is fine — but the amendment artifact should still exist so the reason for the new ticket is visible later.
- When creating mechanical amendment/reconciliation work, prefer these Codex-routed task types instead of generic `orchestration`: `project_change_control`, `project_amendment`, `project_replan`, `plan_rebaseline`, `plan_reconciliation`, `roadmap_reconciliation`, or `architecture_decision`.

### Step 5: Refresh project memory

After you apply the change-control decision, regenerate project context and any relevant retrieval layers so the next executor sees the amended truth instead of stale pre-change context.

## See Also

- [[orchestrator]]
- [[project-plan]]
- [[sync-context]]
