---
type: skill
name: check-projects
description: Reviews project status by aggregating ticket states
inputs:
  - project (optional — specific project slug; if omitted, checks all)
---

# Check Projects

## Instructions

1. **Glob** all files matching `vault/projects/*.md` AND `vault/clients/*/projects/*.md` (for client-scoped projects).
2. **For each project** (or the specified one):
   a. Read the project file.
   b. Extract all ticket references from the task list. Prefer full wiki-link targets such as `[[T-001-write-copy]]`, and support legacy bare references such as `[T-001]` for backwards compatibility.
   c. Read each ticket's frontmatter to get current status.
   d. Calculate progress: `completed / total` tasks.
   e. Identify blockers: any ticket with status `blocked` or `waiting`.
   f. Identify next actions: tickets that are `open` and have no `blocked_by` or whose blockers are all `closed`.

3. **Update the project file**:
   - Check off completed tasks (where ticket status = closed).
   - Update the `status` field:
     - `paused` if the project is intentionally paused by the runner/orchestrator and work remains
     - `active` if work is in progress
     - `blocked` if all remaining tasks are blocked/waiting
     - `complete` if all tasks are closed
   - Update the `updated` date.

   If the project is already marked `paused`, preserve that status unless the caller is explicitly resuming the project.

4. **Return a status report**:

```
## Project: {title}
**Status:** {status} | **Progress:** {completed}/{total} ({percentage}%)
**Due:** {due or "none"}

### Completed
- [x] [[T-001-write-email-copy|T-001]]: Write email copy ✓

### In Progress
- [ ] [[T-002-design-landing-page|T-002]]: Design landing page (in-progress, assigned to agent)

### Blocked / Waiting
- [ ] [[T-003-send-campaign|T-003]]: Send campaign (waiting — needs client approval, [[T-005-client-approval|T-005]])

### Ready to Start
- [ ] [[T-004-set-up-tracking-pixels|T-004]]: Set up tracking pixels (open, no blockers)

### Blockers Summary
- [[T-005-client-approval|T-005]]: Client approval needed (waiting, assigned to human)
```

## When to Run

- Before the orchestrator spawns new agents (to know what's ready)
- After agents report back (to update progress)
- On every orchestrator loop iteration

## See Also

- [[create-project]]
- [[check-tickets]]
- [[orchestrator]]
- [[SCHEMA]]
