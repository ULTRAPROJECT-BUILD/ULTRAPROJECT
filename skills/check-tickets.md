---
type: skill
name: check-tickets
description: Queries tickets by status, project, assignee, or priority
inputs:
  - filter (optional — object with any combo of status, project, assignee, priority, task_type, tags)
  - sort_by (optional — default: priority)
---

# Check Tickets

## Instructions

1. **Glob** all files matching `vault/tickets/T-*.md` AND `vault/clients/*/tickets/T-*.md` (for client-scoped tickets).
2. **Read frontmatter** from each file.
3. **Apply filters** — if a filter field is provided, only include tickets where the frontmatter value matches. Multiple filters are AND-ed.
4. **Sort results** by the `sort_by` field. Priority order: critical > high > medium > low.
5. **Return a summary table** with columns: ID, Title, Status, Priority, Assignee, Project.
6. **Also return counts** by status: open, in-progress, blocked, waiting, closed.

## Filter Examples

- All open tickets: `{ status: "open" }`
- High-priority blockers: `{ status: "blocked", priority: "high" }`
- All code-review tickets: `{ task_type: "code_review" }`
- All tickets for a project: `{ project: "q2-campaign" }`
- My open work: `{ assignee: "agent", status: "in-progress" }`

## Output Format

```
## Tickets (filtered: status=open)

| ID    | Title                  | Status | Priority | Assignee | Project      |
|-------|------------------------|--------|----------|----------|--------------|
| T-003 | Write email copy       | open   | high     | agent    | q2-campaign  |
| T-001 | Set up landing page    | open   | medium   | agent    | q2-campaign  |

**Counts:** 2 open | 0 in-progress | 0 blocked | 0 waiting | 0 closed
```

## Updating a Ticket

To update a ticket's status or add to its work log:
1. Read the ticket file.
2. Update the `status` and `updated` fields in frontmatter. Terminal ticket status is `closed`, never `done`.
3. If the work is actually complete, set `completed` to the same current datetime. If the ticket is being closed without completing the work (for example, denied or canceled), leave `completed` empty or absent.
4. Append a timestamped entry to the `## Work Log` section.

## See Also

- [[create-ticket]]
- [[check-projects]]
- [[SCHEMA]]
- [[orchestrator]]
