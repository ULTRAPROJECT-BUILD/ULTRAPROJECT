---
type: skill
name: vault-status
description: Generates a snapshot overview of the entire vault state — projects, tickets, clients, archive, and system health
inputs:
  - output_path (optional — where to write the snapshot; default: vault/snapshots/_platform/{today}-vault-status.md)
---

# Vault Status

You are generating a point-in-time overview of the vault. This gives any agent a quick "state of the world" without scanning every file.

## When to Run

- At the start of every orchestrator loop (abbreviated version)
- Weekly as a full snapshot
- When the admin requests a `status` pass in chat

## Process

### Step 1: Client Overview

1. Read `vault/clients/_registry.md`.
2. For each client, read their `config.md` and summarize:
   - Status (onboarding, active, paused, churned)
   - ToS accepted?
   - Payment status
   - Active project count

### Step 2: Project Summary

1. Glob all projects: `vault/projects/*.md` and `vault/clients/*/projects/*.md`.
2. For each project, extract from frontmatter: title, status, goal, updated.
3. Run [[check-projects]] logic to get progress (completed/total tasks).
4. Flag any project not updated in 7+ days as potentially stale.

### Step 3: Ticket Summary

1. Run [[check-tickets]] with no filter to get all tickets.
2. Summarize by status: open, in-progress, blocked, waiting, closed.
3. Flag:
   - Tickets `in-progress` for 2+ days (stale)
   - Tickets `blocked` where the blocker is also blocked (deadlock)
   - Tickets assigned to `human` (need admin attention)

### Step 4: Archive Health

1. Read `vault/archive/_index.md` — count archived MCPs and skills.
2. Read `vault/archive/playbooks/_index.md` — count playbooks.
3. Glob `vault/archive/patterns/*.md` — count patterns.
4. Report: "Archive: {X} MCPs, {Y} skills, {Z} playbooks, {W} patterns"

### Step 5: System Health

1. Read [[metering]] for token usage totals.
2. Read [[platform]] for configured limits.
3. Calculate:
   - % of daily invocation target used overall
   - % of monthly invocation budget used per agent from the Agent Credit Pools table
4. Check if any agent-routing thresholds or spending limits are approaching warnings.

### Step 6: Write Snapshot

Write the status to `{output_path}`:

```markdown
---
type: snapshot
title: "Vault Status — {now}"
captured: {now}
agent: vault-status
tags: [status, system]
---

# Vault Status — {now}

## Clients
| Slug | Status | ToS | Payment | Active Projects |
|------|--------|-----|---------|-----------------|
| ... | ... | ... | ... | ... |

**Total:** {count} clients ({active} active, {onboarding} onboarding)

## Projects
| Project | Status | Progress | Last Updated |
|---------|--------|----------|--------------|
| ... | ... | .../... | ... |

**Stale (7+ days):** {list or "none"}

## Tickets
| Status | Count |
|--------|-------|
| Open | {n} |
| In-Progress | {n} |
| Blocked | {n} |
| Waiting | {n} |
| Closed | {n} |

**Needs attention:** {stale tickets, deadlocks, human-assigned}

## Archive
- MCPs: {n} | Skills: {n} | Playbooks: {n} | Patterns: {n}

## System
- Daily invocations: {used}/{target} ({pct}%)
- Agent pools: Claude {pct}% | Codex {pct}% (or disabled)
- Alerts: {any threshold warnings or "none"}
```

## Output

Return:
- Snapshot file path
- Summary counts (clients, projects, open tickets, archive size)
- Any alerts (stale work, deadlocks, budget warnings, human-needed tickets)

## See Also

- [[check-projects]]
- [[check-tickets]]
- [[metering]]
- [[platform]]
- [[orchestrator]]
