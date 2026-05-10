---
type: skill
name: create-project
description: Creates a new project file from a high-level goal (supports client-scoped projects). Tickets are created by project-plan, not this skill.
inputs:
  - goal (required — the high-level objective)
  - title (required — short project name)
  - client (optional — client slug; when provided, creates project in vault/clients/{client}/projects/)
  - due (optional)
  - tags (optional)
---

# Create Project

## Instructions

0. **Determine project location:**
   - If `client` is provided: create the project at `vault/clients/{client}/projects/{slug}.md` and use [[create-ticket]] with `client` parameter for all tickets.
   - If `client` is NOT provided: create at `vault/projects/{slug}.md` and use platform-level tickets.

1. **Assign a global project number (all client-scoped projects):**
   - **Skip numbering** only for platform/internal projects (located in `vault/projects/`, not `vault/clients/*/projects/`). Set `project_number` to empty string and move on.
   - **Every client-scoped project gets a number** — including onboarding projects. The number is the project's identity on the dashboard and in client communications.
   - Read the global project counter at `vault/projects/.counter`.
   - If missing or corrupted: scan ALL project directories (`vault/clients/*/projects/`) for the highest `project_number` in frontmatter. Recreate `.counter` with that value. If no projects have numbers, start at `0`.
   - Increment by 1, write back to `.counter`.
   - Format as zero-padded to at least 3 digits: `001`, `002`, ... `999`, `1000`, etc.
   - This number is global across all clients — it represents total platform project count.
   - **Atomicity:** Project number assignment must be atomic. If the counter changes unexpectedly during a run (e.g., another process incremented it), re-read and re-increment before writing the project file. Never assign a number you didn't just increment.

2. **Create the project file only** — analyze the goal and write the project file with the goal, context, and high-level notes. **Do NOT create tickets here.** The orchestrator will run [[project-plan]] after this to define architecture decisions, decompose into phases, and create tickets. This ensures every project gets explicit planning, architecture decisions, and artifact tracking regardless of size.
   - **Immediately after writing the project file, generate the derived project context layer** so the project shell has a native orientation surface from the first cycle:
     ```bash
     python scripts/build_project_context.py --project-file "{project_file_path}"
     python scripts/build_project_image_evidence.py --project-file "{project_file_path}"
     python scripts/build_project_video_evidence.py --project-file "{project_file_path}"
     python scripts/refresh_project_text_embeddings.py --project-file "{project_file_path}"
     ```
     This creates `{project}.derived/current-context.md`, `{project}.derived/artifact-index.yaml`, `{project}.derived/image-evidence-index.yaml`, and `{project}.derived/video-evidence-index.yaml` in a sibling folder next to the project file. They are derived helpers only — the project file remains canonical. See [[SCHEMA]] → "Project Derived Context".
     If the project goal already names a real code workspace, you may also run:
     ```bash
     python scripts/refresh_project_code_index.py --project-file "{project_file_path}"
     ```
     This is safe when no code workspace exists yet; it no-ops cleanly.
   - If the project shell already includes screenshots, visual proofs, or Stitch outputs, refresh selective visual embeddings too:
     ```bash
     python scripts/refresh_project_image_embeddings.py --project-file "{project_file_path}"
     python scripts/refresh_project_video_embeddings.py --project-file "{project_file_path}"
     ```
     This is safe to call repeatedly. It only refreshes embeddings when the manifest changed and no-ops cleanly when the project has no indexed image/video evidence yet.

3. **Write the project file** at the determined location:

```markdown
---
type: project
title: "{title}"
project_number: "{number or ''}"
status: active
goal: "{goal}"
created: {now}
updated: {now}
due: {due or ""}
owner: orchestrator
tags: {tags or []}
---

# {title}

## Goal
{goal}

## Context
{client requirements, domain notes, any relevant background}

## Plan
(Project plan will be linked here by [[project-plan]] skill)

## Tasks
(Tickets will be listed here as they are created by [[project-plan]] skill)

## Notes
{any context, constraints, or decisions made during planning}
```

3. **Return** the project slug, file path, and client (if scoped). Do NOT return ticket IDs — tickets are created by [[project-plan]], not this skill.

## Principles

- This skill creates the project shell; [[project-plan]] fills it with architecture decisions, phases, and tickets
- The project file is the single source of truth for project status
- When a website project includes "location" or "directions" as a client requirement, treat it as a first-class deliverable with its own section or page (embedded map, address, hours, parking), not just footer content. (Learned from 2026-03-17-location-section-standard-requirement, 2026-03-17)

## See Also

- [[create-ticket]]
- [[orchestrator]]
- [[check-projects]]
- [[SCHEMA]]
