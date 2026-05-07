---
type: skill
name: sync-context
description: Builds a condensed context package for executor agents — architecture decisions, artifact state, recent work
inputs:
  - project (required — project slug)
  - client (optional — client slug)
  - ticket_id (required — the ticket about to be executed, for relevance filtering)
---

# Sync Context

You are building a condensed context package for an executor agent that is about to work on a ticket. The executor has no memory of prior cycles — this context package is its only window into what has been built so far.

**Rule: Be concise. The context package is injected into the executor's prompt. Every unnecessary word burns tokens that the executor needs for actual work. Target 500-1000 words.**

## Augmentation Boundary: Graph-Backed vs Static Sections

The context package assembled by this skill contains two categories of sections.
Understanding this boundary prevents confusion about what the Refactor Engine
integration changes and what it does not.

**Static sections** — sourced from vault project metadata (plan, tickets, briefs).
These exist for every project and are unaffected by the Refactor Engine integration:

| Section                  | Source                                               |
|--------------------------|------------------------------------------------------|
| Architecture Decisions   | Project plan snapshot                                |
| Goal Contract            | Project plan                                         |
| Active Assumptions       | Project plan Assumption Register                     |
| Pending Amendments       | `project-amendment` snapshots + project file         |
| Image Evidence          | `{project}.derived/image-evidence-index.yaml`        |
| Video Evidence          | `{project}.derived/video-evidence-index.yaml`        |
| Code Workspaces         | `artifact-index.yaml` → `code_workspaces`            |
| Drift / Rehearsal        | latest drift-detection and rehearsal snapshots       |
| Current Phase            | Project plan frontmatter / phase table               |
| What Exists Already      | Project plan artifact manifest                       |
| Recent Work Summary      | Closed ticket work logs                              |
| Quality Bar              | Creative brief or project plan                       |
| Proof Strategy           | Creative brief                                       |
| Open Questions           | Project plan                                         |
| From Your Dependencies   | `blocked_by` ticket results                          |

**Graph-backed section** — sourced from the Refactor Engine knowledge graph via
`scripts/refactor_bridge.py`. Only present for existing-codebase projects:

| Section       | Source                                                         |
|---------------|----------------------------------------------------------------|
| Code Context  | AST-derived entities, callers, callees, interface contracts    |

Key points:

1. **The graph augments — it does not replace.** Static sections always appear.
   Code Context is additive and only appears when conditions are met
   (`has_existing_codebase: true` AND `file_paths` set on the ticket).
2. **Static project metadata cannot come from AST analysis.** Architecture
   decisions, phase definitions, artifact manifests, and quality criteria are
   human/agent-authored and live in vault markdown files.
3. **The graph replaces only the implicit "read the code yourself" step** that
   executor agents currently perform ad-hoc. It provides structural code
   understanding without requiring the executor to navigate the codebase.
4. **Graceful fallback.** If the bridge script fails or returns `{"ok": false}`,
   the context package falls back to static-only — the Code Context section is
   simply omitted. A bridge failure never blocks executor dispatch.

## When to Use

The orchestrator calls this skill before spawning an executor agent, when the project has a project plan (a snapshot with `subtype: project-plan`).

## Process

### Step 0: Read the Project File

Before reading the plan, read the project file itself to check for existing-codebase flags:
- Client-scoped: `vault/clients/{client}/projects/{project}.md`
- Platform: `vault/projects/{project}.md`

If the project has derived context artifacts in the `<slug>.derived/` sibling folder, read them first:
- `{project}.derived/current-context.md`
- `{project}.derived/artifact-index.yaml`
- `{project}.derived/image-evidence-index.yaml`
- `{project}.derived/video-evidence-index.yaml`

Treat these as orientation aids, not source of truth. They tell you what matters now and which files are authoritative, but any claim you pass to the executor must still be grounded in the canonical project file, plan, tickets, briefs, or snapshots.
If the orchestrator refreshed project-scoped text embeddings, prefer `python3 scripts/search_project_hybrid.py --project-file {project_file} "{query}"` for project-local conceptual retrieval before broad vault search.
If the task is visual or screenshot-driven, assume the orchestrator may also have refreshed selective image embeddings for the project and prefer `python3 scripts/search_media.py --project {project}` over broad global media search.
If the task is code-touching and the artifact index includes `code_workspaces`, prefer the registered code roots there and use GitNexus MCP for structural code questions after orienting from the current context. If the orchestrator refreshed `python3 scripts/refresh_project_code_index.py --project-file {project_file}`, treat GitNexus as ready; otherwise, it may still be pending.
If a curated Nexus/Obsidian vault is open, you may still use Nexus MCP for backlinks or link traversal, but it is optional and should not replace the project-scoped retrieval path.

Extract from the frontmatter:
- `has_existing_codebase` — if `true`, this project targets an existing codebase and Step 4b applies
- `target_codebase_path` — the path to the existing codebase (required when `has_existing_codebase: true`)

If neither field is present, this is a greenfield project — skip Step 4b entirely.

### Step 1: Read the Project Plan

Find and read the project plan:
- Client-scoped: `vault/clients/{client}/snapshots/{project}/*-project-plan-*.md`
- Platform: `vault/snapshots/{project}/*-project-plan-*.md`

Extract:
- **Architecture decisions** — the full table
- **Goal Contract** — mission, rigor tier, evaluator, success metrics, primary risks, ownership split, proof shape, and workstream labels
- **Assumption Register** — especially unresolved or high-risk assumptions relevant to the current ticket
- **Pending amendments** — any `project-amendment` artifacts or `## Pending Amendments` entries that change what the ticket should build or prove
- **Image Evidence** — top referenced screenshots / QC slides / walkthrough frames when the task has a visual or screenshot-driven proof surface
- **Drift / Rehearsal** — latest drift detection or rehearsal packet when the project is approaching a risky transition
- **Current phase** — which phase is active, its goal and exit criteria
- **Artifact manifest** — what exists and where
- **Open questions** — relevant unresolved questions

### Step 2: Read Recent Completed Work

Find closed tickets for this project (in the appropriate tickets directory). Read the **last 10 closed tickets** (by completion date). For each, extract:
- Title
- A 1-2 sentence summary of what was produced (from the work log's final entry or COMPLETE checkpoint)
- Key artifact paths

Skip tickets that are clearly unrelated to the current ticket's domain (e.g., don't include payment tickets when the executor is building game levels).

### Step 3: Read the Current Ticket's Dependencies

Check the current ticket's `blocked_by` list. For each dependency:
- Read what it produced (final work log entry)
- Note artifact paths that the current ticket should consume or build on

### Step 4: Read the Creative Brief

If a project-level creative brief exists, extract the key quality criteria:
- Proof Strategy — evaluator lens, proof posture, false-pass risks, rehearsal lenses, drift sentinels, supplement trigger, and gate impact
- Deliverable format/structure
- Visual/tonal standards
- Acceptance criteria
- Anti-patterns to avoid

### Step 4b: Code Context from Knowledge Graph (existing-codebase projects only)

**This step only applies when the project file has `has_existing_codebase: true` and `target_codebase_path` set.** Skip entirely for greenfield projects.

If the project targets an existing codebase, augment the context package with AST-aware code context from the Refactor Engine knowledge graph:

1. Read the current ticket's `file_paths` field (list of file paths the ticket will touch, relative to the target codebase).
2. Run the bridge script to get token-budgeted code context:
   ```bash
   python3 scripts/refactor_bridge.py build-context \
     --target {target_codebase_path} \
     --files {comma_separated_file_paths} \
     --token-budget 4000
   ```
3. If the bridge returns `{"ok": true}`, extract the context data. If it returns `{"ok": false}`, log the error and fall back to the standard context package (no graph section). Never let a bridge failure block the executor.
4. From the bridge output, build a `## Code Context` section containing:
   - For each entity in the ticket's files: name, kind, complexity, line range
   - Callers: who calls this code (name + file)
   - Callees: what this code calls (name + file)
   - Interface contracts: how callers use this code
5. If the ticket has no `file_paths` field, skip this step (the executor doesn't know which files it will touch yet — this is common for discovery/spike tickets).

**Augmentation boundary:** This step adds a new `## Code Context` section to the context package. It does NOT replace any of the existing static sections (Architecture Decisions, Current Phase, What Exists Already, Recent Work Summary, From Your Dependencies, Quality Bar, Open Questions). Those sections come from the project plan and ticket history — they cannot be derived from AST analysis. The Code Context section provides structural understanding of the codebase that would otherwise require the executor to read and navigate files ad-hoc.

### Step 5: Synthesize the Context Package

Assemble a context package in this format:

```
## Project Context for {ticket_id}

### Architecture Decisions (binding)
{table of decisions — include ALL of them, these are non-negotiable}

### Goal Contract
{mission, rigor tier, evaluator, success metrics, primary risks, ownership split, proof shape, and the workstream labels this ticket most directly serves}

### Active Assumptions
{only unresolved / validating / high-risk assumptions relevant to this ticket}

### Image Evidence
{only the screenshots, slides, or walkthrough images this ticket/review most likely needs — paths plus what they prove}

### Current Phase: {phase name}
Goal: {phase goal}
Exit criteria: {what must be true}
Your ticket's role: {how this ticket contributes to the phase goal}

### What Exists Already
{artifact manifest — paths and descriptions, most recent first}

### Recent Work Summary
{1-2 sentence summaries of the last 5-10 relevant closed tickets}

### From Your Dependencies
{what the blocking tickets produced that you should use or build on}

### Code Context
{ONLY present for existing-codebase projects with file_paths. Contains entity summaries, callers, callees, and interface contracts from the knowledge graph. Omit this entire section for greenfield projects.}

### Quality Bar
{key criteria from the creative brief, if applicable}

### Proof Strategy
{only the parts of the brief's proof strategy this ticket needs to honor — evaluator lens, false-pass risks, rehearsal lenses, drift sentinels, supplement trigger, and required evidence modes}

### Drift / Rehearsal
{latest drift findings or rehearsal packet that should shape this ticket, if any}

### Open Questions Relevant to You
{any unresolved questions that might affect this ticket}
```

### Step 6: Return

Return the context package text. The orchestrator will inject it into the executor's prompt. Do NOT save this as a vault file — it is ephemeral prompt content.

## Relevance Filtering

Not everything in the project history is relevant to every ticket. Apply these filters:
- **Architecture decisions**: Always include all of them.
- **Artifacts**: Include all from the current phase, plus any from prior phases that the current ticket's domain depends on.
- **Closed tickets**: Prioritize tickets from the same phase and the same domain. A "build website" ticket doesn't need the full history of "design logo concepts" unless the logo is an input.
- **Creative brief**: Always include if it exists.
- **Open questions**: Only include if they could affect this ticket's work.

## Size Budget

The context package should be **500-1000 words**. If the project has a long history, summarize aggressively. The executor can always read specific files if it needs more detail — the context package just tells it what exists and where to look.

If the artifact manifest alone exceeds 500 words (very large project), group artifacts by category and list only the most recent/relevant ones. Add a note: "Full manifest in project plan at {path}."

## Error Handling

- If no project plan exists, return an empty context package with a note: "No project plan found. Executor should read the project file and gather-context skill for orientation."
- If the plan exists but the artifact manifest is empty (Phase 1, early tickets), still return the architecture decisions and phase context — those are the most important parts.

## See Also

- [[project-plan]]
- [[orchestrator]]
- [[gather-context]]
- [[creative-brief]]
