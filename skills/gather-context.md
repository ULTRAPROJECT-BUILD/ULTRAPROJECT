---
type: skill
name: gather-context
description: Structured context-gathering protocol — traverses wiki links, backlinks, and related files before an agent begins work
inputs:
  - ticket_id (required — the ticket about to be worked on)
  - client (optional — client slug for client-scoped work)
  - depth (optional — how many link levels to traverse, default: 2)
---

# Gather Context

You are gathering context before starting work on a ticket. Do NOT begin executing the task until this process is complete. The vault is your memory — this skill ensures you actually read it.

## Process

### Step 1: Read the Ticket

1. Read the ticket file for `{ticket_id}`.
2. Extract from frontmatter: project slug, blocked_by, assignee, tags, priority.
3. Note any `[[wiki links]]` in the body text — these are direct dependencies.

### Step 2: Read the Project and Client Context

1. Read the project file referenced in the ticket's `project` field.
   - If client-scoped: `vault/clients/{client}/projects/{project}.md`
   - If platform-level: `vault/projects/{project}.md`
2. Understand the goal, task list, and where this ticket fits in the overall plan.
3. Check the project's `## See Also` for related files.
4. If client-scoped, check for `vault/clients/{client}/preferences.md`. If it exists, read it — this tells you how the client likes to work, what formats they prefer, what approaches succeeded before, and what to avoid. Apply relevant preferences to your work.
5. If `{project}.derived/current-context.md` and `{project}.derived/artifact-index.yaml` exist in the project's `<slug>.derived/` sibling folder, read them first as the fast orientation layer. If the artifact index includes `code_workspaces` and your task is code-touching, note which workspace is primary and whether GitNexus appears ready before you start wandering through the codebase manually.
6. If the ticket is deep, review-heavy, or otherwise cross-cutting — and it is not an explicitly clean-room lane like `stress_test` or `artifact_polish_review` — run 1-3 targeted project-scoped hybrid retrieval queries before broad repo wandering.
   - Use `python3 scripts/search_project_hybrid.py --project-file {project_file} "{query}"` once you know the project file path.
   - Derive queries from the ticket title, acceptance criteria, and current phase goal.
   - Capture only a short retrieval digest: which artifacts, proofs, screenshots, reviews, or briefs look relevant and why.

### Step 2.5: Read Project Plan (if exists)

Check for a project plan snapshot:
- Client-scoped: `vault/clients/{client}/snapshots/{project}/*-project-plan-*.md`
- Platform: `vault/snapshots/{project}/*-project-plan-*.md`

If a project plan exists:
1. Read it in full.
2. Extract the **Architecture Decisions** table. These are **binding constraints** for your work. Do not make choices that contradict them without creating a decision record first.
3. Note the **current phase** — its goal, exit criteria, and how your ticket contributes.
4. Read the **Artifact Manifest** — what files already exist and where. Use them; do not recreate from scratch.
5. Check **Open Questions** — if any are relevant to your ticket, note them but do not resolve them unilaterally.

The project plan is the authoritative source for architectural context. It takes precedence over inferences you might make from individual tickets.

### Step 3: Follow Links (Depth Traversal)

Starting from the ticket and project, follow `[[wiki links]]` and `## See Also` sections:

1. **Depth 1** — read every file linked from the ticket and project.
2. **Depth 2** (default) — read the See Also sections of those files too.
3. For each file read, note:
   - Relevant constraints or rules (especially from config and legal docs)
   - Skills you'll need to use
   - MCPs you'll need to call
   - Decisions that set precedent for this work

Do NOT follow links into tickets or projects unrelated to your task. Stay within the scope of your assignment.

### Step 4: Check Backlinks (optional via Nexus MCP)

If a curated Nexus/Obsidian vault is available:
1. Search for backlinks to the ticket — what other files reference this ticket?
2. Search for backlinks to the project — are there related decisions, lessons, or snapshots?
3. Check if any `waiting` tickets are waiting on YOUR ticket — your work may unblock others.

If Nexus MCP is unavailable, skip this step — the project-derived context and link traversal from Steps 1-3 cover the critical paths.

### Step 5: Check Relevant Lessons and Decisions

1. Scan for lessons related to this project or domain:
   - Client-scoped: `vault/clients/{client}/lessons/`
   - Platform-level: `vault/lessons/`
2. Scan for decisions that constrain this work:
   - Client-scoped: `vault/clients/{client}/decisions/`
   - Platform-level: `vault/decisions/`
3. Only read files with matching project or relevant tags — don't read everything.

### Step 6: Build Context Summary

Assemble a mental model before acting:

- **Goal:** what the ticket asks for
- **Project context:** where this fits in the bigger picture
- **Skills needed:** which skill files to follow during execution
- **MCPs needed:** which tools you'll call
- **Constraints:** legal rules, config limits, client status, budget
- **Prior art:** relevant lessons, decisions, or playbook matches
- **Downstream impact:** what tickets or processes depend on your output

## Depth by Priority

Not every ticket needs the full traversal. Scale context-gathering to the work:

| Ticket Priority | Depth | Steps to Run |
|----------------|-------|--------------|
| low | 0 | Steps 1-2 only (ticket + project) |
| medium | 1 | Steps 1-3 (add one level of link traversal) |
| high / critical | 2 | Steps 1-5 (full traversal, backlinks, lessons) |
| New goal (no ticket yet) | 2 | Full — you're planning, not executing |

This keeps token usage proportional to the complexity and risk of the work.

## When to Use

- **Always** before an executor agent starts work on a ticket (depth by priority)
- **Always** when the orchestrator is assessing a new goal (full depth)
- **Optionally** when resuming work on a project after a pause (depth 1)

## Output

This skill doesn't produce a file — it produces understanding. The agent should be able to answer:
1. What exactly am I doing?
2. What rules constrain how I do it?
3. What related work has been done before?
4. What depends on me finishing this?

## See Also

- [[orchestrator]]
- [[SCHEMA]]
- [[SYSTEM]]
- [[check-tickets]]
- [[check-projects]]
- [[match-playbooks]]
