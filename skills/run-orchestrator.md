---
type: skill
name: run-orchestrator
description: Entry point — how to kick off the orchestration system
inputs:
  - goal (optional — high-level objective for a new project)
  - project (optional — project slug to resume)
  - client (optional — client slug for client-scoped runs)
  - request_context (optional — operator-provided context for a new client/project)
---

# Running the Orchestrator

## Starting a New Platform Project

```
Read SYSTEM.md for system context, then read skills/orchestrator.md.
Execute the orchestrator with this goal: "{your goal here}"
```

The orchestrator will create a project in `vault/projects/`, create tickets, spawn agents, and loop until complete.

## Starting a Client-Scoped Project

```
Read SYSTEM.md for system context, then read skills/orchestrator.md.
Execute the orchestrator with client: "{client-slug}" and goal: "{goal}"
```

This creates the project and tickets in `vault/clients/{client-slug}/projects/` and `vault/clients/{client-slug}/tickets/`.

## Resuming an Existing Project

```
Read SYSTEM.md for system context, then read skills/orchestrator.md.
Resume the orchestrator for project: "{project-slug}"
```

For client-scoped projects:
```
Read SYSTEM.md for system context, then read skills/orchestrator.md.
Resume the orchestrator for client: "{client-slug}" project: "{project-slug}"
```

## Creating A New Client-Scoped Project

```
Read SYSTEM.md for system context, then read skills/create-project.md.
Create a client-scoped project from this operator-provided request:
  Client: {client-slug}
  Request: {request_context}
```

## Chat-Native Operation

Start, pause, and resume orchestration directly from Codex or Claude. This clean distribution does not include scheduled polling, external-message polling, or always-on behavior.

## Manual Operations

**Create a ticket:**
```
Read SYSTEM.md and skills/create-ticket.md.
Create a ticket: title="{title}" project="{slug}" priority=high body="{description}"
```

**Create a client-scoped ticket:**
```
Read SYSTEM.md and skills/create-ticket.md.
Create a ticket: client="{slug}" title="{title}" project="{project}" body="{description}"
```

**Check ticket status:**
```
Read SYSTEM.md and skills/check-tickets.md.
Check all tickets for project: "{slug}"
```

**Search archive for prior art:**
```
Read SYSTEM.md and skills/match-playbooks.md.
Search for playbooks matching: industry="{industry}" channels=["{channel}"]
```

**Source a capability:**
```
Read SYSTEM.md and skills/source-capability.md.
Source an MCP for: "{description}"
```

## See Also

- [[orchestrator]]
- [[check-tickets]]
- [[create-ticket]]
- [[match-playbooks]]
- [[source-capability]]
- [[SYSTEM]]
