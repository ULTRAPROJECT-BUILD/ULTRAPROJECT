---
type: skill
name: project-plan
description: Creates and maintains a living architectural plan for every project — architecture decisions, anchor phases, capability lanes, dynamic wave tracking, artifact state
inputs:
  - project (required — project slug)
  - client (optional — client slug)
  - mode (optional — "create" or "update"; default: "create")
  - goal (required for create — the high-level objective)
  - client_answers (optional — client's clarification answers for context)
  - research_context_path (optional — explicit research-context snapshot override; normally Step 0 resolves or creates this)
---

# Project Plan

You are creating or updating a living architectural plan for a project. This plan is the persistent document that carries architecture decisions, phase structure, capability state, dynamic attack waves, and artifact state across orchestrator cycles. Every executor agent will read this plan before starting work.

**Rule: Architecture decisions in this plan are binding. No executor may contradict them without creating a decision record and updating this plan first.**

## When to Use

The orchestrator triggers this skill for **every new project** after creating the project file:
- **Create mode:** A new project needs architecture decisions, phased decomposition, and Phase 1 tickets. Even small projects benefit from explicit decisions and artifact tracking — use 1-2 phases for simple work.
- **Update mode:** A phase completes and the project needs to advance to the next phase with new tickets.

## Step 0: Research Context Gate (MANDATORY)

Project-plan owns currentness research. The orchestrator creates or resumes the project shell, then invokes this skill; this skill must run the research gate before any architecture decisions, phase design, ticket creation, or plan update.

1. Resolve `project_file_path`, `project`, `goal`, and `snapshots_path` before planning. Use the same snapshot location the plan will use:
   - Client-scoped: `vault/clients/{client}/snapshots/{project}`
   - Platform client workspace: `vault/clients/_platform/snapshots/{project}`
   - Legacy platform: `vault/snapshots/{project}`
2. Get timestamps from the machine-local clock, never from inference:
   ```bash
   date +"%Y-%m-%dT%H:%M"
   date +%Y-%m-%d
   ```
3. Run the deterministic trigger helper and write both reports into the project snapshots directory:
   ```bash
   python3 scripts/research_context_trigger.py --project-file "{project_file_path}" --goal "{goal}" --json-out "{snapshots_path}/{date}-research-context-trigger-{project}.json" --markdown-out "{snapshots_path}/{date}-research-context-trigger-{project}.md"
   ```
4. STOP if no `*-research-context-trigger-{project}.json` output exists, if the trigger helper cannot be run, or if the trigger decision is `error`. Project-plan must not produce architecture decisions without a trustworthy trigger decision. Surface the trigger failure and ask the orchestrator/operator to fix the project file or helper failure first.
5. If the trigger decision is `required` or `refresh_required`, run [[research-context]] immediately before Step 1. Pass `project`, `client`, `goal`, `project_file_path`, `snapshots_path`, `trigger_reason`, `previous_snapshot_path` when present, and `force_refresh: true` for `refresh_required`.
6. STOP if research was required but no final `*-research-context-{project}.md` snapshot exists after [[research-context]] runs. A working file, budget ledger, trigger report, or checker report is not enough.
7. If the trigger decision is `optional` or `skip`, proceed without new external research, but still record the trigger report path and decision in `## Current Research Inputs`.
8. If an explicit `research_context_path` input is provided, read it after the trigger decision and verify that it is a final research-context snapshot for this project. Do not let an explicit path bypass a required trigger or required refresh.
9. If a research-context snapshot exists, read only the claim ledger, executive synthesis, downstream use, low-confidence flag, budget/frontmatter counts, and relevant category implications. Do not paste raw research into the plan.
10. If the snapshot has `low_confidence: true`, currentness claims are hypotheses, not facts. Convert any used low-confidence or inferred claims into `## Assumption Register` rows or `## Open Questions` entries with validation methods.
11. Always write `## Current Research Inputs` in the plan before `## Architecture Decisions`, even when research was skipped. This section is the mechanical proof that project-plan ran Step 0.

## Create Mode

### Step 1: Analyze the Goal

1. Read the project goal and any client answers/requirements.
2. Identify the **foundational architecture decisions** that must be made before any execution begins. These are choices that constrain everything downstream — technology stack, language, framework, art style, data model, output format, delivery medium, etc.
3. **Outcome-first thinking**: Before making architecture decisions, separate the client's **desired outcome** from their **proposed method**. The client says "scrape website X" — the outcome is "get dataset Y." The client says "build me a React app" — the outcome is "interactive tool that does Z." Always ask: is there a better, faster, more reliable, or more legal way to achieve the same outcome? If yes, propose it. The client cares about results, not implementation details.

4. **Legal and ethical check**: If the client's proposed method involves bypassing security measures, violating Terms of Service, scraping protected sites, creating fake accounts, or anything legally questionable — do NOT proceed with that method. Instead:
   a. Identify the underlying outcome the client wants.
   b. Research legitimate alternatives that achieve the same result (public APIs, open datasets, official bulk downloads, licensed services).
   c. **Draft a client-facing alternative proposal** for operator-mediated sending. **Skip for practice client** (`is_practice: true`) — log the decision instead of drafting external communication. Explain: what they asked for, why that specific method is problematic, and how the alternative achieves the same outcome — often better. Be professional and helpful, not preachy.
   d. If the client accepts the alternative, proceed with the project using the legitimate method.
   e. If the client pushes back and insists on the problematic method, **then** escalate to admin through the project/ticket log and chat response with the full context (what the client wants, what you proposed, why they pushed back). Let the admin make the call.
   f. Never auto-reject the project — reject the method, propose a better path, and let the client decide.

5. **Client fidelity check**: For each decision, compare it against what the client explicitly asked for. If a decision would **deviate from a stated client requirement** (e.g., client asked for "third-person 3D" but you're choosing "top-down 2D"), you MUST:
   a. First, try to find a way to deliver what they asked for — source or build the needed tools (Three.js, Blender, Unity export, etc). The platform can build any MCP or skill it needs.
   b. If after genuine effort you determine it's truly not feasible, write an admin escalation explaining: what the client asked for, why it's difficult, what you'd propose instead, and ask for approval BEFORE making the tradeoff. **Skip external communication for practice client** — log the decision in the project file instead.
   c. **Never silently downgrade a client requirement.** Practical tradeoffs are fine when approved — silent deviations are not.
4. For each decision, write a clear choice and rationale. If a decision cannot be made yet, add it to Open Questions.

### Step 1aa: Goal Compiler (MANDATORY)

Before the plan hardens, explicitly compile the request into a `## Goal Contract`.

The Goal Contract is the upstream mission contract for the rest of the project. It is not a duplicate of the Mission Alignment Map — it is the planning-time version of the same truth.

1. Determine the **rigor tier**:
   - `lightweight` — small, low-risk, low-novelty, low-blast-radius work
   - `standard` — normal multi-phase client/platform work
   - `frontier` — capability-waves, admin-priority, high-novelty, high-risk, or trust-sensitive work
2. Write the Goal Contract with these required fields:
   - `Rigor tier`
   - `Mission`
   - `Primary evaluator`
   - `Mission success`
   - `Primary success metrics`
   - `Primary risks`
   - `Human-owned decisions`
   - `Agent-owned execution`
   - `Proof shape`
   - `In scope`
   - `Out of scope`
   - `Partial-coverage rule`
3. Add a `### Goal Workstreams` table under the Goal Contract with columns:
   - `Goal / Workstream`
   - `Type`
   - `Priority`
   - `Success Signal`
   - `Evaluator`
   - `Scale / Scope`
4. Use the Goal Workstream labels as the canonical labels for `[TRACES: ...]` tags in phase exit criteria. This makes mission traceability mechanical instead of fuzzy.
5. Keep this adaptive:
   - `lightweight` plans can be concise, but the Goal Contract still must exist
   - `frontier` plans must be explicit about scale, evaluator lens, and what partial coverage would and would not honestly mean

### Step 1ab: Assumption Register (MANDATORY)

Surface the hidden bets the project depends on. Do not hide them in Open Questions or prose alone.

1. Create a `## Assumption Register` section in the plan.
2. Use a table with these required columns:
   - `ID`
   - `Assumption`
   - `Category`
   - `Risk`
   - `Validation Method`
   - `Owner`
   - `Target Phase/Gate`
   - `Status`
   - `Evidence / Resolution`
3. Valid statuses:
   - `open`
   - `validating`
   - `resolved`
   - `accepted-risk`
   - `deferred`
   - `invalidated`
4. For `frontier` plans, at least one real unresolved or validating assumption should usually exist. If none do, either the project is not actually frontier or the register is not honest yet.
5. High-risk assumptions must have a concrete validation method and a target phase/gate. "We'll know later" is not sufficient.

### Step 1a: Playbook Usage Contract (MANDATORY when prior art exists)

Playbooks are prior art, not default architecture. Before any archived project shapes the plan, establish the reuse boundary.

1. Determine whether the project is **frontier/high-novelty**. Treat it as frontier if any of the following are true:
   - enterprise/platform/infrastructure build
   - extreme scale or safety claim
   - new category for the system
   - architecture materially beyond the validated envelope of the archived playbooks
   - admin-priority work where the system is expected to originate rather than imitate
2. Start from first principles:
   - write the architecture from the current goal, constraints, and required capabilities
   - decide what the project must prove on its own
   - only then compare that draft against playbook prior art
3. If playbooks exist, set a project-level `reuse_mode`:
   - `pattern_only` — lessons, risks, process shape, anti-patterns only
   - `component_reuse` — bounded modules/checklists/scripts may be reused with fresh rationale
   - `template_allowed` — only for genuinely repetitive, low-novelty work
4. **Frontier rule:** frontier projects default to `pattern_only`. Do not upgrade beyond that unless the plan explicitly justifies why the old playbook's scope, risk, and constraints are truly aligned.
5. Write two required sections into the plan:
   - `## Playbook Usage Contract`
   - `## Why This Cannot Just Be The Playbook`
6. These sections must state:
   - which playbooks matched
   - the allowed reuse mode for each
   - what can be imported safely
   - what must be re-proven here
   - what architectural/product/scale claims are forbidden from inheritance

### Step 1b: Systems Design (MANDATORY for complex projects)

**Trigger: If the project involves 3+ interacting systems, procedural generation, a data model with relationships, or novel technical challenges the platform hasn't solved before — do NOT skip to ticket creation. Design the architecture first.**

**Skip: If the project is a single-deliverable task using proven skills (one website, one communication campaign, one report) — go straight to Step 2. Simple projects don't need systems design.**

This step is genre-agnostic. A roguelike game needs it (loot ↔ inventory ↔ combat ↔ procedural generation). A SaaS prototype needs it (auth ↔ API ↔ database ↔ frontend). A consulting engagement needs it (research ↔ analysis ↔ recommendations ↔ deliverables). The pattern is the same.

**1. Systems map** — identify every system/module and how they connect:
   - What are the major components? (e.g., combat system, loot system, dungeon generator, UI)
   - What data flows between them? (e.g., weapon stats → damage calculation → health system → death trigger)
   - What's the shared data model? (e.g., Item schema used by loot, inventory, shop, and equipment)
   - Draw the dependency graph: which systems MUST exist before others can be built?

**2. Technical risks** — identify what's hard and unproven:
   - What has the platform never done before? (e.g., procedural level generation, real-time multiplayer, complex state machines)
   - What could fail in a way that invalidates the entire architecture?
   - What are the performance-critical paths?

**3. Vertical slice strategy** — define a minimal end-to-end path through the whole system:
   - For a game: one level, one character, 3 enemies, one boss, core combat, basic UI. Playable start to finish.
   - For a web app: one user flow, auth → main screen → primary action → result. Deployed and working.
   - For a consulting engagement: one section fully researched, analyzed, and formatted to final quality.
   - The vertical slice proves the architecture works before scaling to full scope.

**4. Spike tickets** — for each technical risk, plan a spike (time-boxed prototype) to prove feasibility before committing. The spike builds the riskiest piece in isolation. If the spike fails, redesign before wasting tickets on dependent systems.

Include the systems map, risks, vertical slice definition, and spike list in the project plan document under a `## Systems Design` section. This becomes binding architecture — executors read it before every ticket.

### Step 1c: Refactor Engine Bridge Analysis (CONDITIONAL — existing codebase only)

**Trigger: The project file frontmatter contains `has_existing_codebase: true` AND a `target_codebase_path` field.**

**Skip: If `has_existing_codebase` is absent, false, or the project is greenfield — skip this step entirely and proceed to Step 2. Greenfield projects are completely unaffected by this step.**

When working with an existing codebase, the Refactor Engine bridge provides domain decomposition and hotspot data that dramatically improve phase planning. Use it to understand the codebase structure before defining phases.

1. **Run bridge analyze** to get domain and hotspot data:
   ```bash
   python3 scripts/refactor_bridge.py analyze --target <target_codebase_path>
   ```
   The command outputs JSON: `{"ok": bool, "data": {"domains": [...], "hotspots": [...], "entity_count": N, "relationship_count": N, "average_complexity": N}, "error": str|null}`

2. **Handle failures gracefully.** If the bridge command exits non-zero, returns `"ok": false`, or throws any error:
   - Log the failure in the plan's Open Questions: `"Bridge analyze failed: {error}. Planning without domain data."`
   - Fall back to standard planning without domain data — proceed to Step 2 as if this step was skipped.
   - Do NOT block plan creation on a bridge failure.

3. **If analyze succeeds**, use the data to inform planning:
   - **Domains**: The `domains` array shows natural module boundaries in the codebase (community clusters). Use these to group related work into the same phase rather than scattering changes across unrelated modules.
   - **Hotspots**: The `hotspots` array shows high-complexity, high-change-frequency entities. Prioritize phases so that hotspot-heavy areas are addressed earlier — these are where bugs concentrate and where refactoring has the highest ROI.
   - **Complexity stats**: `average_complexity` and `entity_count` help calibrate ticket count estimates and phase sizing.
   - Include a summary of the domain/hotspot analysis in the plan under `## Systems Design` or a new `## Codebase Analysis` section (whichever fits the project).

4. **Plan a "Phase 0: Index & Analyze" phase.** When `has_existing_codebase: true`, the first phase is always Phase 0 to index the target codebase via Refactor Engine. This ensures the knowledge graph is built before any code changes begin:
   ```
   ### Phase 0: Index & Analyze (active)
   **Goal:** Index the target codebase into the Refactor Engine knowledge graph for domain-aware planning and safe refactoring
   **Entry criteria:** Target codebase path confirmed, Refactor Engine bridge available
   **Exit criteria:** `.refactor-engine/` directory created in target codebase [EXECUTABLE], entity_count > 0 in index output [EXECUTABLE], domain/hotspot summary recorded in plan [EXECUTABLE]
   **Tickets:** (created after plan QA)
     - Index target codebase via `python3 scripts/refactor_bridge.py index --target <target_codebase_path>` (task_type: code_build)
   ```
   Set `current_phase: 0` in the plan frontmatter when Phase 0 exists.

### Step 2: Decompose into Anchor Phases, Capabilities, and Waves

1. **Choose an execution model first:**
   - `classic` — use for straightforward, repeatable, or low-uncertainty work where the path is mostly knowable upfront. These plans can use **3-6 detailed phases**.
   - `capability-waves` — use for frontier, admin-priority, extreme-scale, existing-codebase, or multi-front campaigns where the real path will be discovered through proofs, failures, and redesigns. These plans use **3-5 anchor phases** plus a capability register and dynamic waves.
2. **All projects still need numbered phases.** The difference is how detailed they should be:
   - **Classic:** phases can be detailed milestone slices.
   - **Capability-waves:** phases are **anchor phases only** — stable macro stages such as Discovery, Capability Assault, Proof Gauntlet, Final Verification, Delivery. Do NOT pretend you already know the full tactical sequence.
3. **Phase 1 vertical-slice rule:**
   - For `classic` projects, **Phase 1 MUST be the vertical slice** — not "setup" or "scaffolding." Phase 1 produces a playable/usable/viewable end-to-end path through the core experience.
   - For `capability-waves` projects, Phase 1 must still produce an honest proving move, but it does **not** need to be a fake product slice when the real mission is platform or capability truth. Existing-platform campaigns may use Phase 1 for the first assault/proof lane (for example, Chromium native-code truth or backend isolation) if that is the real first thing that must be proven.
4. **Spike tickets go in Phase 0 (Discovery)** if there are unresolved technical risks. Phase 0 is optional — only use it when there's genuine uncertainty that could invalidate the architecture. Otherwise go straight to Phase 1. **Note:** If Step 1c already created a Phase 0 (Index & Analyze) for an existing-codebase project, spike tickets should be added to Phase 0 alongside the index ticket, or placed in Phase 0.5 if the spikes depend on the index completing first.
5. For each phase, define:
   - **Goal**: What this phase produces (one sentence)
   - **Entry criteria**: What must be true before this phase starts
   - **Exit criteria**: What must be true before moving to the next phase — be specific and verifiable. **Every exit criterion must be tagged with its executability classification** (see below).
   - **Estimated ticket count**: Rough estimate (will be refined when the phase starts)
6. Phases should be ordered so that earlier phases reduce uncertainty for later ones. Put the riskiest/most uncertain work early.
7. **Capability register (MANDATORY for `capability-waves` projects):**
   Track the core capability lanes the project must drive to the target verdict. Use a table under `## Capability Register` with one row per lane:
   - `Capability`
   - `Current Verdict`
   - `Target Verdict`
   - `Proof Status`
   - `Blocking Subsystem`
   - `Active Wave`
   - `Next Proof`
   This is the living truth for campaign projects. The plan is incomplete if the hard mission capabilities are only implied by phases and never made explicit.
8. **Dynamic wave log (MANDATORY for `capability-waves` projects):**
   Add a `## Dynamic Wave Log` table. Waves are the tactical units that may be inserted, merged, reordered, or retired as proof results come in. For each wave, track:
   - `Wave`
   - `Status` (`active`, `planned`, `complete`, `failed`, `superseded`)
   - `Anchor Phase`
   - `Capability Lanes`
   - `Purpose`
   - `Success Signal`
   - `Tickets`
   Only define the **current wave and the next 1-2 likely waves** concretely. Later work should remain hypotheses, not fake certainty.
9. **Wave discipline for `capability-waves`:**
   - The active wave, not the whole anchor phase, is the thing that gets ticketized and executed next.
   - When a proof fails, update the capability register and dynamic wave log before pretending the original sequence still makes sense.
   - If a capability remains below target after a wave closes, create or activate the next wave **inside the same phase** unless the anchor phase itself is genuinely complete.
10. **Criterion classification (MANDATORY for all exit criteria in all phases):**
   Every exit criterion must be tagged:
   - `[EXECUTABLE]` — can be verified in the current build environment with available tools
   - `[INFRASTRUCTURE-DEPENDENT]` — requires external service, live database, display server, or hardware not guaranteed in the build environment. **Must include fallback evidence** (e.g., "unit tests cover this code path" or "mock-based integration test verifies the handler").
   - `[MANUAL]` — requires human judgment (visual taste, UX feel, accessibility with screen reader). Deferred to admin usability review phase.
   Gate reviewers evaluate only EXECUTABLE criteria as hard gates. INFRASTRUCTURE-DEPENDENT criteria pass if fallback evidence exists. MANUAL criteria are deferred. This prevents wasted gate iterations on untestable items.
11. **Mission traceability (MANDATORY for all exit criteria in all phases):**
   Every exit criterion must include a `[TRACES: {goal}]` tag that maps it back to a specific mission goal, workstream, or stated requirement from the original client/admin request. Use the exact goal label (e.g., `[TRACES: WS-2 relationship-resolution scalability]` or `[TRACES: "mobile-responsive lead capture"]`). After writing all exit criteria for all phases:
   - List every non-negotiable goal/workstream from the original request.
   - For each goal, verify at least one exit criterion across all phases traces to it.
   - **If any mission goal has zero exit criteria tracing to it, the plan is incomplete.** Add exit criteria that prove the goal is met, or escalate to admin: "Goal '{goal}' cannot be met within project scope. Here's why. Awaiting admin decision to descope or extend."
   - **Exit criteria that accept known-partial results on a core mission goal must be explicitly flagged as `[PARTIAL-COVERAGE]` and justified.** The justification must explain what would be required for full coverage and why it's not achievable in this project. The phase gate will evaluate whether the partial coverage is honestly justified or is scope avoidance.
12. **Exit criteria fidelity check (MANDATORY after writing all exit criteria):**
   After all exit criteria are defined, apply the same fidelity check from Step 1 (item 5) to the exit criteria themselves — not just architecture decisions. For each exit criterion, ask: "Does this criterion accept less than what the client/admin explicitly asked for?" If yes:
   a. First, try to write a stronger criterion that matches the stated requirement.
   b. If a stronger criterion is genuinely infeasible, write an admin escalation explaining: what the admin asked for, what the exit criterion accepts instead, why the gap exists, and ask for approval BEFORE finalizing the plan. **Skip external communication for practice client** — log the decision in the project file instead.
   c. **Never silently set an exit criterion below the stated mission.** Achievable-but-insufficient criteria are worse than honest escalation — they create the illusion of progress while missing the point.
13. **For projects producing code/software deliverables, insert a Verification Manifest phase between the last build phase and the QA phase.** Other domains may use the same phase when the deliverable needs mixed proof types (builds, inspections, runtime proofs, external validations, manual checks):
   ```
   ### Phase N: Verification Manifest & Proof Execution (planned)
   **Goal:** Generate verification manifest from brief, execute mixed proof items against the built deliverable, fix all CODE_DEFECT failures
   **Entry criteria:** All build phases complete
   **Exit criteria:** 100% EXECUTABLE P0 pass, 100% EXECUTABLE P1 pass, verification results saved with proof matrix + screenshot evidence [EXECUTABLE]
   **Tickets:** (created when this phase starts)
     - Verification manifest generation (Claude, task_type: verification_manifest_generate; `test_manifest_generate` legacy alias allowed)
     - Verification manifest execution (Claude, task_type: verification_manifest_execute; `test_manifest_execute` legacy alias allowed)
     - Fix tickets from failures (Codex, task_type: code_fix) — created dynamically
   ```

### Step 3: Write the Plan

Save the plan to the appropriate snapshots directory:
- Client-scoped: `vault/clients/{client}/snapshots/{project}/{date}-project-plan-{project}.md`
- Platform: `vault/snapshots/{project}/{date}-project-plan-{project}.md`

**Immediately after writing the plan**, link it from the project file's `## Plan` section:
```
Project plan: [[{plan filename}]]
```
This ensures the orchestrator can discover the plan during recovery if project-plan is interrupted before ticket creation.

**Immediately after writing the plan**, refresh the derived project context layer so the new plan, phase state, and authoritative artifacts are available to the orchestrator and future executors:
```bash
python3 scripts/build_project_context.py --project-file "{project_file_path}" --project-plan "{plan_path}"
python3 scripts/build_project_image_evidence.py --project-file "{project_file_path}"
python3 scripts/build_project_video_evidence.py --project-file "{project_file_path}"
python3 scripts/refresh_project_text_embeddings.py --project-file "{project_file_path}"
```
This updates `{project}.derived/current-context.md`, `{project}.derived/artifact-index.yaml`, `{project}.derived/image-evidence-index.yaml`, and `{project}.derived/video-evidence-index.yaml` in the project's `<slug>.derived/` sibling folder. They are derived helper artifacts only — the project file, plan, tickets, briefs, and snapshots remain canonical. See [[SCHEMA]] → "Project Derived Context".
If the plan now points at a real code workspace, also run:
```bash
python3 scripts/refresh_project_code_index.py --project-file "{project_file_path}"
```
This is stateful and only re-indexes code when the relevant workspace HEAD changed. If the plan points at a project-owned scaffolded app/workspace that now exists but is not yet a git repo, this step may bootstrap it into a local repo first so later code tasks can use real code intelligence instead of permanent fallback mode.
If this project already has visual evidence (QC screenshots, walkthrough frames, Stitch references, delivery screenshots), also run:
```bash
python3 scripts/refresh_project_image_embeddings.py --project-file "{project_file_path}"
python3 scripts/refresh_project_video_embeddings.py --project-file "{project_file_path}"
```
This is stateful and cheap to call. It refreshes only when the visual corpus changed and otherwise exits as a no-op.
The text embedding refresh is also stateful. It re-embeds only when the curated project semantic corpus changed, so calling it after plan updates is safe and cheap.

Use this template (note: **Tickets** fields are left as "(created after plan QA)" — tickets are NOT created yet):

```markdown
---
type: snapshot
subtype: project-plan
title: "Project Plan — {project title}"
project: "{project-slug}"
client: "{client or _platform}"
execution_model: {classic|capability-waves}
current_phase: {0 if Phase 0 exists, else 1}
total_phases: {N}
captured: {now}
agent: project-plan
tags: [plan, architecture]
---

# Project Plan — {title}

## Current Research Inputs

- **Trigger report:** {path to `*-research-context-trigger-{project}.json`}
- **Trigger decision:** {required|refresh_required|optional|skip} — {reason}
- **Research-context snapshot:** {research_context_path or "not required"}
- **Confidence:** {low_confidence false/true or "not available"}
- **Cost and coverage:** {total_websearch} WebSearch, {total_webfetch} WebFetch; per-category counts summarized from research-context frontmatter when available, or "not applicable"
- **Planning implications:** {cited claim IDs and concise implications that affect architecture, tooling, phases, risks, or proof; "none" when skipped}
- **Assumptions from low-confidence research:** {claim IDs converted into Assumption Register rows or Open Questions, or "none"}

## Architecture Decisions

| Decision | Choice | Rationale | Decided |
|----------|--------|-----------|---------|
| {decision} | {choice} | {why} | {date} |

## Playbook Usage Contract

- **Project novelty:** {frontier/high-novelty or repeatable}
- **Reuse mode:** {pattern_only | component_reuse | template_allowed}
- **Matched playbooks:** {list with quality classification + reuse cap, or "none"}
- **Safe imports:** {lessons, bounded components, checklists, scripts, process shape}
- **Forbidden inheritance:** {architecture proof, scale proof, product shape, claims beyond validated envelope}

## Why This Cannot Just Be The Playbook

- {What is materially different about this project}
- {What the archived work does not prove here}
- {What must be originated or re-proven from scratch}

## Goal Contract

- **Rigor tier:** {lightweight|standard|frontier}
- **Mission:** {the real non-negotiable mission of the project}
- **Primary evaluator:** {who or what ultimately judges success}
- **Mission success:** {what would make this honestly done}
- **Primary success metrics:** {the leading metrics or success signals that matter most}
- **Primary risks:** {the main failure modes or trust risks that could invalidate success}
- **Human-owned decisions:** {what still requires human judgment, approval, or taste}
- **Agent-owned execution:** {what the platform is expected to own end-to-end}
- **Proof shape:** {what kind of proof will close the mission honestly}
- **In scope:** {what this project will deliberately cover}
- **Out of scope:** {what this project will deliberately not claim}
- **Partial-coverage rule:** {when partial coverage would be honest vs dishonest}

### Goal Workstreams

| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |
|-------------------|------|----------|----------------|-----------|---------------|
| {WS-1 label} | {functional|quality|risk|delivery} | {critical|high|medium} | {what proves it} | {who judges it} | {what scale this proves} |

## Assumption Register

| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |
|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|
| {A-001} | {hidden bet the project depends on} | {product|technical|proof|operational|data|user} | {low|medium|high|critical} | {how this will be tested or closed} | {orchestrator|brief|QC|human|specific ticket/phase owner} | {Phase N / brief gate / QC / delivery gate} | {open|validating|resolved|accepted-risk|deferred|invalidated} | {current note} |

## Systems Design
{Include if Step 1b was triggered — omit for simple projects}

**Systems map:** {components and how they connect — data flows, dependency graph}
**Technical risks:** {what's hard, what could break the architecture}
**Vertical slice:** {minimal end-to-end path that proves the architecture works}
**Spikes needed:** {time-boxed prototypes for unresolved risks, if any}

## Capability Register
{Include when `execution_model: capability-waves`; omit for classic plans}

| Capability | Current Verdict | Target Verdict | Proof Status | Blocking Subsystem | Active Wave | Next Proof |
|------------|-----------------|----------------|--------------|--------------------|-------------|------------|
| {e.g. relationship_resolution} | {Partial} | {Ready} | {bounded Chromium subset only} | {resolver / parser bridge} | {Wave A} | {Chromium shard rerun with native resolver} |

## Dynamic Wave Log
{Include when `execution_model: capability-waves`; omit for classic plans}

| Wave | Status | Anchor Phase | Capability Lanes | Purpose | Success Signal | Tickets |
|------|--------|--------------|------------------|---------|----------------|---------|
| {Wave A} | {active} | {Phase 1} | {relationship_resolution, native_parser} | {first honest tactical attack} | {non-zero C++ cross-file relationships on Chromium shard} | {(created after plan QA)} |

## Phases

{FOR capability-waves projects: use 3-5 anchor phases only. Do NOT script a 10-step tactical sequence. The wave log carries the dynamic attack order.}

{IF spikes needed from Systems Design:}
### Phase 0: Discovery/Spikes (active)
**Goal:** Resolve technical risks before committing to architecture
**Phase brief:** none
**Advance grade threshold:** A
**Entry criteria:** Systems design complete, risks identified
**Exit criteria:** All spike tickets closed [EXECUTABLE], architecture validated [EXECUTABLE]
**Tickets:** (created after plan QA)
{END IF — set current_phase: 0}

{IF no spikes:}
### Phase 1: Vertical Slice (active)
**Goal:** {one complete end-to-end path through the core experience}
**Phase brief:** none
**Advance grade threshold:** {A for client work and any frontier/admin-priority capability phase; B only when a lower-stakes internal phase truly does not justify another remediation cycle}
**Entry criteria:** Architecture decisions made{, Phase 0 complete if it exists}
**Exit criteria:** {specific, verifiable conditions — something playable/usable/viewable. Tag each with executability: [EXECUTABLE], [INFRASTRUCTURE-DEPENDENT], or [MANUAL]. Tag each with mission traceability: [TRACES: {goal}]. Use [PARTIAL-COVERAGE] with justification if a criterion accepts less than the full mission goal.}
**Runtime verification:** Build compiles, launches without crash, core path is interactive (screenshot evidence required)
**Tickets:** (created after plan QA)
{END IF — set current_phase: 1}

### Phase 2: {name} (planned)
**Goal:** {one sentence}
**Phase brief:** {none|optional|required}
**Advance grade threshold:** {A|B|manual}
**Entry criteria:** Phase 1 complete.
**Exit criteria:** {specific, verifiable conditions. Tag each with executability: [EXECUTABLE], [INFRASTRUCTURE-DEPENDENT], or [MANUAL]. Tag each with mission traceability: [TRACES: {goal}].}
**Runtime verification:** New functionality works + Phase 1 core path still works (regression check, screenshot evidence)
**Tickets:** (created when Phase 2 starts)

{repeat for remaining phases}

{IF project produces code/software deliverables or mixed proof execution is warranted:}
### Phase N-2: Verification Manifest & Proof Execution (planned)
**Goal:** Generate verification manifest from brief, execute against built deliverable, fix all CODE_DEFECT failures
**Phase brief:** required
**Advance grade threshold:** A
**Entry criteria:** All build phases complete
**Exit criteria:** 100% EXECUTABLE P0 pass, 100% EXECUTABLE P1 pass, verification results saved with proof matrix + screenshot evidence [EXECUTABLE]
**Tickets:** (created when this phase starts)
{END IF}

### Phase N-1: Quality Assurance (planned)
**Goal:** Self-review and QC of all deliverables
**Phase brief:** {optional for simple work, required when the phase has special evidence/media/review contracts}
**Advance grade threshold:** A
**Entry criteria:** All build phases complete{, verification manifest phase complete if applicable}
**Exit criteria:** QC verdict PASS [EXECUTABLE], phase gate A [EXECUTABLE]
**Tickets:** (created when this phase starts)

{IF stress test criteria met per Error Handling section:}
### Phase N: Adversarial Stress Test (planned)
**Goal:** Independent clean-room agent tries to break the deliverable — feeds bad input, kills mid-operation, hits scale limits, tests the core value proposition end-to-end
**Phase brief:** required
**Advance grade threshold:** A
**Entry criteria:** QC phase complete (Phase N-1 passed)
**Exit criteria:** Stress test verdict PASS (zero blockers, zero majors) or PASS with caveats (majors disclosed to client and accepted) [EXECUTABLE]. Fix tickets landed and re-tested if FAIL.
**Tickets:** (created when this phase starts)
{END IF}

### Phase N+1: Artifact Polish Review (planned)
**Goal:** Clean-room consumption review of the finished artifact pack — catch first-impression, coherence, trust, and finish issues that builder-side review and QC can miss
**Phase brief:** required
**Advance grade threshold:** A
**Entry criteria:** QC passed{, stress test passed if applicable}
**Exit criteria:** Review pack built [EXECUTABLE], artifact polish review verdict PASS [EXECUTABLE], grade A [EXECUTABLE]
**Tickets:** (created when this phase starts)

### Phase N+2: Admin Usability Review (planned)
**Goal:** Human review of all deliverables before client delivery — catch visual, UX, and "feel" issues that automated QC cannot detect
**Phase brief:** optional
**Advance grade threshold:** manual
**Entry criteria:** Artifact polish review passed, credibility gate passed, pre-delivery gate passed
**Exit criteria:** Admin has reviewed deliverables and marked APPROVED, or created revision tickets for issues found [MANUAL]
**Tickets:** (created when this phase starts — one ticket: "Admin usability review" assigned to `human`, with instructions to open/run all deliverables and check visual quality, UX flow, and overall impression)

### Phase N+3: Delivery (planned)
**Goal:** Deliver to client, await acceptance
**Phase brief:** optional
**Advance grade threshold:** manual
**Entry criteria:** Admin usability review APPROVED
**Exit criteria:** Client APPROVE received (or auto-accepted after 144h) [MANUAL]
**Tickets:** (created when this phase starts)

## Artifact Manifest

| Artifact | Path | Produced by | Date |
|----------|------|-------------|------|
| (none yet) | | | |

## Open Questions

- [ ] {question that cannot be decided yet — note which phase should resolve it}

## Plan History

- {now}: Plan created. Pending Plan QA before ticket creation.
```

### Step 4: Plan QA Gate (MANDATORY — plan must pass before tickets are created)

The project plan is the most important artifact in the pipeline — a bad plan perfectly executed is still a bad deliverable. The plan must pass Plan QA **before any tickets are created**.

**Note:** This is the canonical plan QA gate. The orchestrator's plan review gate (orchestrator.md Phase 1) should defer to this step — if project-plan already ran Step 4, the orchestrator skips its own redundant review.

1. **Determine the passing threshold:**
   - **Client work projects:** A (no exceptions)
   - **Platform/internal projects:** A
   - **Hard practice projects:** B
   - **Extreme practice projects:** C
   - **Medium practice projects:** skip this gate (single-phase, no systems design needed). Write `- {now}: Plan QA — skipped (medium practice)` to Plan History so the orchestrator's recovery logic can distinguish "gate skipped" from "gate pending"

2. **Gather source requirements** for the review. The plan reviewer needs the original requirements to verify plan fidelity:
   - **Always include the project file** (which contains `## Goal` and `## Context`) as a baseline requirements source
   - If `client_answers` were provided, write them to the snapshots directory (`{snapshots_dir}/plan-qa-requirements-{project}.md`) so they persist across chat-native cycles, and reference BOTH the project file AND the answers file — client answers supplement the goal, they don't replace it
   - Additionally, search for request artifacts (exclude `*project-plan*` files to avoid self-comparison):
     - `vault/clients/{client}/snapshots/incoming/` for operator-provided request artifacts
     - `vault/clients/{client}/tickets/` for clarification/discovery tickets
   - **Fallback:** If no request artifact exists (common for platform/internal projects), the project file alone is sufficient

2b. **Run the playbook-overreach checker** when prior art is in scope, especially for frontier/high-novelty projects:
   ```bash
   python3 scripts/check_playbook_overreach.py --plan {plan_path} --project {project_file_path}
   ```
   - If the checker fails, revise the plan before treating QA as complete.
   - The checker is a structural guardrail; Plan QA still runs and can catch subtler overreach that the script misses.

2c. **Run the quality-contract checker** before Plan QA:
   ```bash
   python3 scripts/check_quality_contract.py --project-file "{project_file_path}" --project-plan "{plan_path}" --json-out "{snapshots_path}/{date}-quality-contract-{project}.json" --markdown-out "{snapshots_path}/{date}-quality-contract-{project}.md"
   ```
   - If this exits non-zero, revise the plan before treating QA as complete.
   - This is the mechanical guardrail for Goal Contract + Assumption Register integrity. Plan QA still runs and can catch subtler mission/proof issues that the script misses.

2d. **Run the plan compliance checker** (rubric-letter-for-letter mechanical floor):
   ```bash
   python3 scripts/check_plan_compliance.py --plan "{plan_path}" --json-out "{snapshots_path}/{date}-plan-compliance-{project}.json" --markdown-out "{snapshots_path}/{date}-plan-compliance-{project}.md"
   ```
   - If this exits non-zero, revise the plan before running the model gate. Required structural elements (Current Research Inputs, Architecture Decisions, frontier sections, Capability Register/Dynamic Wave Log when applicable, exit-criteria taxonomy tags, reverse trace coverage, [PARTIAL-COVERAGE] tag enforcement) are non-negotiable — they are the rubric items that the cross-context model reviewer is *most* likely to misclassify as "non-blocking tightening." This script removes that decision from the model.
   - The model gate in Step 3 evaluates qualitative judgment (architecture soundness, scale matching, mission alignment); the mechanical floor is set here.

2e. **Include research-context in Plan QA.** The Plan QA prompt must tell the reviewer to inspect `## Current Research Inputs`. When a `{research_context_path}` exists, the reviewer must also read it and verify that cited current facts may inform architecture, low-confidence or inferred claims become assumptions/open questions, and no plan decision overclaims current tooling or vendor capability without a fresh citation.

3. **Run plan review** via the gate reviewer role (auto-routed per `agent_routing.agent_mode` in [[platform]]). Always reference requirements by file path, never inline raw text:
   <!-- GATE-ONLY: --force-agent is correct here because this is a gate/review, not ticket execution -->
   ```bash
   python3 scripts/agent_runtime.py run-task --force-agent gate_reviewer --task-type code_review --prompt "Review the project plan at {plan_path} for project {project}. The original requirements are at {requirements_file_path}. Also read the mechanical quality-contract report at {snapshots_path}/{date}-quality-contract-{project}.md AND the plan compliance report at {snapshots_path}/{date}-plan-compliance-{project}.md. Evaluate: (1) are architecture decisions sound and well-reasoned, (2) is the systems design complete if applicable, (3) are phases ordered correctly with vertical slice first or, for capability-waves campaigns, as honest anchor phases rather than fake tactical certainty, (4) are exit criteria specific and testable, (5) does the plan faithfully represent the requirements without silent downgrades — compare against the source, (6) are technical risks identified and addressed, (7) are open questions tracked, (8) is the planned ticket decomposition reasonable, (9) does the plan set up for enterprise-grade output per deliverable-standards.md, (10) for frontend design work, does the plan assign the right `design_mode` (`stitch_required`, `concept_required`, or `implementation_only`) instead of forcing a blanket rule, (11) for existing public-surface redesigns, does the plan force a greenfield concept pass with composition anchors before implementation, (12) does the plan use playbooks as bounded prior art rather than as silent architecture proof — check for a Playbook Usage Contract, a Why This Cannot Just Be The Playbook section, and project-specific reasoning that originates before it inherits, (13) GOAL CONTRACT AUDIT: the plan must contain a Goal Contract and Goal Workstreams that make the mission, evaluator, scope, and scale explicit. If the Goal Contract is present but merely duplicates the goal without clarifying the real mission or evaluator lens, grade down. (14) ASSUMPTION REGISTER AUDIT: critical hidden bets should be explicit, especially for frontier/admin-priority work. If high-risk assumptions are absent or hand-wavy, grade down. (15) MISSION ALIGNMENT AUDIT: read the original requirements file and extract every non-negotiable goal, workstream, or stated requirement. For each goal, verify that at least one exit criterion across all phases has a [TRACES: {goal}] tag mapping to it and that the traces map back to Goal Workstreams in the Goal Contract. If any goal has zero traceability, grade F — the plan misses the mission. If any exit criterion uses [PARTIAL-COVERAGE] on a core mission goal, verify the justification explains what full coverage would require and why it is infeasible — unjustified partial coverage on a core goal is scope avoidance and should be graded F. SCALE MATCHING: For each exit criterion with a [TRACES:] tag, verify the criterion proves at a scale consistent with the traced goal language. If the goal uses scale language (millions of lines, enterprise-scale, Chromium-class, at scale) and the criterion proves at a materially smaller scale without [PARTIAL-COVERAGE] justification, grade F — underwhelming targets dressed as mission alignment are scope avoidance. If the original requirements contain no explicit non-negotiable goals (e.g., simple practice projects), this check passes automatically, (16) DYNAMIC CAMPAIGN STRUCTURE AUDIT: if this is a frontier/high-novelty/admin-priority/extreme-scale project, verify the plan uses `execution_model: capability-waves`, includes a Capability Register and Dynamic Wave Log, keeps phases at anchor-phase granularity, and avoids pretending the full tactical path is already known, and (17) RESEARCH-CONTEXT AUDIT: verify `## Current Research Inputs` records the trigger decision and either a final research-context snapshot or an explicit skip/optional reason. If a snapshot exists, verify cited current facts inform only appropriate architecture/tooling/proof choices, low-confidence or inferred claims are represented as assumptions/open questions, and no plan decision overclaims current tooling or vendor capability without fresh citation. If the plan scripts detailed late-game tactics for a frontier campaign instead of using waves, grade it down — that is planning theater, not honest orchestration. RUBRIC LETTER-FOR-LETTER ENFORCEMENT: A missing rubric-mandated tag or required section (including `## Current Research Inputs`, [PARTIAL-COVERAGE] on a workstream declared partial in Goal Contract, [TRACES: WS-N] traceability on every workstream, [EXECUTABLE]/[INFRASTRUCTURE-DEPENDENT]/[MANUAL] taxonomy on every exit criterion) is REVISE — NOT 'non-blocking tightening.' Mechanical compliance gaps that the plan-compliance-report flagged as failures must be fixed in the plan and the report re-run before grading A. Apply the rubric letter-for-letter; mechanical compliance is the floor, qualitative judgment is the ceiling. Grade A-F. Passing threshold: {threshold}. If below threshold, list specific improvements needed. Write review to {snapshots_path}/{date}-plan-review-{project}.md"
   ```

4. **Grade must meet the threshold.** If gate reviewer grades below the passing threshold:
   - Revise the plan based on the plan reviewer's feedback
   - Re-run the review
   - Repeat until the plan meets or exceeds the threshold
   - Do NOT proceed to Step 5 until the plan passes

5. **Update Plan History** after QA passes:
   ```
   - {now}: Plan QA — gate reviewer grade: {grade}. {brief summary of feedback if any revisions were needed}
   ```

### Step 5: Create First Phase Tickets

**Only run this step after the plan has passed Plan QA in Step 4.**

1. **If Phase 0 (Index & Analyze) exists from Step 1c (existing-codebase project):** set `current_phase: 0` in the plan. Create the index ticket: "Index target codebase via Refactor Engine bridge" with `task_type: code_build`, acceptance criteria: `.refactor-engine/` directory created and `entity_count > 0`. If spikes also exist, include them in Phase 0 or create a Phase 0.5. The orchestrator will advance to Phase 1 when all Phase 0 tickets close.
2. **If Phase 0 (Discovery/Spikes) exists (greenfield with technical risks):** set `current_phase: 0` in the plan. Create spike tickets for Phase 0. The orchestrator will advance to Phase 1 when all spikes close.
3. **If no Phase 0:** set `current_phase: 1` and create Phase 1 (vertical slice) tickets.
4. Decompose the active work into specific tickets using [[create-ticket]].
   - **Execution-model rule:** If `execution_model: capability-waves`, read the `## Dynamic Wave Log` first. Only the **active wave** gets concrete tickets now. Later waves remain hypotheses until activated. Keep the tickets attached to the current anchor phase's `**Tickets:**` field for compatibility, but let the wave log be the source of tactical truth.
   - **Advance-grade rule:** Every phase block must declare `**Advance grade threshold:**`. Use `A` by default for client work, frontier/admin-priority campaigns, capability-upgrade anchor phases, proof gauntlets, QA, stress, and polish. Use `B` only for lower-stakes internal/support phases where another remediation cycle would add little truth value. Use `manual` for human-approval-only phases that do not advance via the automated gate review.
   - **Master-brief rule:** Before creating any phase-scoped creative-brief ticket, verify that the project already has a project-scoped creative brief (master contract). If it does not, create a project-scoped `Creative brief` ticket FIRST and block the phase brief plus all remaining active-phase tickets behind it. The phase brief becomes an addendum, not the root contract. The master brief ticket itself must start with `blocked_by: []` and must NEVER be blocked by the phase brief it governs, even if you attach phase/wave metadata for grouping.
   - **Phase-brief rule:** Read the active phase block before creating tickets. If the phase declares `**Phase brief:** required`, create a phase-scoped creative-brief ticket FIRST for that phase. The remaining phase tickets must be blocked by that brief ticket until it closes and passes the normal creative-brief gate. If the phase declares `optional`, create a phase brief only when the phase has a materially different evaluator lens, proof contract, artifact/media contract, or anti-pattern set than the governing project brief. Do NOT create reciprocal brief dependencies: project brief -> phase brief is allowed; phase brief -> project brief is not.
   - **Wave-supplement rule:** For `execution_model: capability-waves`, do NOT assume one phase brief automatically governs every later wave. If no phase-scoped brief exists for the phase yet, the project brief governs by default. If one or more phase-scoped briefs already exist, verify that the active wave is actually covered before creating its non-brief tickets. Run `python3 scripts/check_wave_brief_coverage.py` with the project/phase/active-wave context. If it fails, create a wave supplement creative-brief ticket FIRST, set that ticket's `wave` to the active wave, and block the rest of the wave behind it. The supplement brief should record `covered_waves` in frontmatter so later wave resolution stays mechanical.
   - **Fan-out rule for deep independent runs:** If the active phase includes 3 or more largely independent repo/workspace/shard/unit jobs with the same execution shape, do NOT default to one giant deep ticket. Prefer:
     - one child ticket per independent unit
     - one aggregation ticket that depends on the children and composes the final report/evidence artifact
     - bounded parallel batches when memory or shared-state limits matter
     Example: six independent repo re-index/evidence runs should usually become six repo tickets plus one aggregate summary ticket, not one monolithic "re-index all 6 repos" ticket.
   - **Code ticket type rule:** If a ticket's primary work is implementing or modifying code, set `task_type: code_build` (not `build`).
   - **Cleanup ticket type rule:** If a ticket's primary work is bounded non-code cleanup, do NOT lazily use `general`. Choose the narrow cleanup type that matches the work:
     - `artifact_cleanup` for stale artifact refresh, proof-pack/report wording alignment, stale status cleanup, review-pack consistency fixes, and supersession-note/documentation cleanup tied to artifacts
     - `receipt_cleanup` for JSON receipt cleanup, command normalization, and machine-readable evidence metadata cleanup
     - `docs_cleanup` for README/docs truth-alignment and wording-only documentation fixes
     These routes intentionally feed Gemini. Use them only for low-risk bounded cleanup work, not for planning, gate review, strategy, or any ticket that changes code.
   - **Frontend design rule:** If a ticket creates or materially redesigns a user-facing UI surface (landing page, dashboard, admin panel, web/mobile/desktop screen, design-system work, visual polish), set `ui_work: true`, choose a `design_mode`, and add tag `ui-design`. Use `stitch_required: true` plus tag `stitch-required` only when the chosen `design_mode` is `stitch_required`.
   - **Design-mode selection rule:** Use `stitch_required` for existing public-surface redesigns, rejected visual work, or high-ambiguity/high-drift multi-screen product UI. Use `concept_required` for greenfield public surfaces and other user-facing design work that needs a real concept but not full Stitch governance. Use `implementation_only` only for low-risk polish or follow-through on an already-approved design/source of truth.
   - **Public-surface rule:** For landing pages, homepages, marketing sites, pricing pages, and other public-facing surfaces, also set `public_surface: true` and tag `public-surface`. These surfaces must clear a visual-narrative bar, not just a correctness bar.
   - **Existing-surface redesign rule:** If the ticket is redesigning an already-existing user-facing surface in an existing codebase, also set `existing_surface_redesign: true` and tag `existing-surface-redesign`. Existing-surface redesigns must not use the current page as the design source of truth.
   - **Page-contract rule:** For top-level nav surfaces such as Account, Settings, Billing, Dashboard, and Admin, also set `page_contract_required: true` and tag `page-contract-required`.
   - **Route-family rule:** For top-level/internal operator-console surfaces such as Pending Review, Handoff, Memory Browser, Trust Ledger, Audit Timeline, Live Watch, Agent Console, Retrieval / Context, Knowledge Graph, or other primary product routes where family consistency matters, also set `route_family_required: true` and tag `route-family-required`. These routes must not improvise generic admin layouts.
   - **Decomposition rule for public-facing UI:** If the phase materially redesigns a public-facing surface, the phase decomposition must separate design definition from implementation. At minimum: one design-owning ticket (brief/Stitch/IA contract) and one implementation ticket blocked by it.
   - **Greenfield concept rule for existing public surfaces:** If the redesign targets an existing public-facing surface, the decomposition must explicitly force a concept-first pass before implementation. The design-owning ticket defines the new concept, composition anchors, and replace-vs-preserve contract as if no current layout existed; the implementation ticket maps that concept back into the current codebase afterward.
5. **The vertical slice phase still follows the full quality pipeline** — creative brief → build → self-review → QC → artifact polish review. The slice is smaller in scope but identical in process. Don't skip the brief, QC, or polish review just because it's a slice.
   - For `design_mode: stitch_required`, the creative brief must include Stitch visual targets and the deliverable must carry `.stitch/` artifacts into QC.
   - For `design_mode: concept_required`, the creative brief must still define the visual direction concretely and QC must compare runtime screenshots against that concept.
   - For public-facing UI, the brief must also include a Visual Quality Bar, Composition Anchors, and Narrative Structure section.
   - For existing public-surface redesigns, the brief must also include a Replace vs Preserve section.
   - For route-family-governed operator surfaces, the brief must also include a Route Family section plus Composition Anchors that define same-product-family parity mechanically.
   - For top-level nav surfaces, the brief must include a Page Contracts section.
6. For complex tickets that will require iterative work, set `complexity: deep` in the ticket frontmatter.
7. Do NOT create tickets for later phases yet. Phase advancement is handled by the **orchestrator's phase gate check**, which calls this skill in update mode when all current-phase tickets close.
8. **Update the plan** with the created ticket IDs in the appropriate phase's **Tickets** field, and update Plan History:
   ```
   - {now}: Phase {current_phase} tickets created: {ticket IDs}.
   ```

### Step 6: Verify Project Link

Confirm the plan reference was added in Step 3. If not (e.g., resuming after interruption), add it now:
```
Project plan: [[{plan filename}]]
```

## Update Mode

Called when a phase completes **or** when a capability-waves project needs to re-plan the active wave after new proof results.

### Step 1: Read Existing Plan

Run Step 0 first when update mode will change architecture decisions, activate a new phase/wave, or create new tickets. If Step 0 refreshes research and it materially changes tools, vendors, deprecated patterns, current best practices, evidence expectations, or assumptions, update `## Current Research Inputs`, `## Assumption Register`, and affected architecture/phase sections before creating tickets.

Read the project plan snapshot. Verify the current phase's exit criteria are actually met by checking closed tickets and their results.

### Step 2: Advance Phase or Re-Plan Wave

1. **Classic execution model:** mark the completed phase as `(complete)`, increment `current_phase`, and mark the next phase as `(active)`.
2. **Capability-waves execution model:** read the Capability Register and Dynamic Wave Log before changing anything.
   - If the active wave closed, do NOT immediately assume the handoff is clean. First run:
     ```bash
     python3 scripts/check_wave_handoff.py --project-plan "{plan_path}" --tickets-dir "{tickets_dir}" --phase "{current_phase}" --search-root "{client_root}/snapshots"
     ```
     Interpret it as a light wave gate:
     - `PASS + GREEN` = close the wave and activate the next wave normally if the anchor phase still has unresolved capability targets.
     - `PASS + YELLOW` = close the wave, activate the next wave, but create the new wave's supplement creative brief first and block its build/review tickets behind that brief.
     - `FAIL + RED` = keep the current wave active and create remediation tickets for the failed wave-closeout issues instead of advancing.
   - If the active wave closed and one or more in-scope capabilities are still below target, keep the current anchor phase active, mark the old wave `complete`/`failed`/`superseded`, activate or insert the next wave, and keep `current_phase` unchanged.
   - If a failed proof revealed a new blocker or invalidated the old approach, update the capability row(s), insert or reorder waves, and create tickets only for the newly active wave.
   - Only advance `current_phase` when the current anchor phase's exit criteria are truly met, the capability register shows that the in-phase capabilities have either hit target or have been explicitly handed off to later anchor phases in the updated wave plan, **and** the latest phase gate grade meets the phase block's `**Advance grade threshold:**`.

### Step 3: Update Artifact Manifest

Read the closed tickets from the completed phase or completed wave. For each ticket that produced artifacts, add entries to the Artifact Manifest with paths and dates.

### Step 4: Refine and Create Next Phase Tickets

1. Re-read the next phase's goal and exit criteria in light of what was actually built in the previous phase or wave.
2. Resolve any Open Questions that can now be answered. Add new architecture decisions if needed.
3. If `execution_model: capability-waves`, update the Capability Register first. Be explicit about what changed:
   - Which capability moved closer to target
   - Which capability is still blocked
   - Which proof failed or passed
   - Which wave is now active
4. Decompose the next unit of work into specific tickets using [[create-ticket]].
   - **Execution-model rule:** For `capability-waves`, create tickets for the active wave only. Do not generate a speculative backlog for later waves unless the wave log explicitly says they are already active/planned and necessary now.
   - **Advance-grade rule:** Preserve the current phase's declared `**Advance grade threshold:**` unless the phase's role changed materially during re-planning. If you lower a threshold from `A` to `B`, add an explicit justification in Plan History explaining why the stricter gate would be wasteful rather than quality-protective.
   - **Master-brief rule:** Before creating a new phase-scoped creative-brief ticket in update mode, verify that a project-scoped creative brief already exists for the project. If not, create that project-scoped brief first and block the phase brief plus the remaining new tickets behind it.
   - **Phase-brief rule:** If the next phase block says `**Phase brief:** required`, create a phase-scoped creative-brief ticket for the next phase first and block the remaining next-phase tickets behind it. Use this for phases with a meaningfully different proof or review lens (verification, QA/evidence packaging, clean-room stress, artifact polish, delivery packaging). If the phase says `optional`, create the phase brief only when the previous phase changed the shape of what this phase must prove.
   - **Wave-supplement rule:** In capability-wave update mode, every newly activated wave must be checked against the current brief stack before you spawn its execution tickets. If no phase-scoped brief exists for the phase, the project brief governs by default. If phase-scoped briefs do exist, run `python3 scripts/check_wave_brief_coverage.py` with the current phase and active wave. When it reports that the wave is uncovered, create a wave supplement creative-brief ticket before any build/review tickets for that wave and block the new wave behind it.
   - **Wave handoff rule:** Use `python3 scripts/check_wave_handoff.py` as the mechanical wave closeout check whenever you are closing one wave and activating the next inside the same anchor phase. Treat `PASS + GREEN` as a normal handoff, `PASS + YELLOW` as "new wave must start behind a supplement brief," and `FAIL + RED` as "do not hand off yet."
   - **Fan-out rule for deep independent runs:** When the next phase contains multiple independent repo/workspace/shard/unit jobs, decompose them into child tickets plus one aggregate ticket rather than a single sequential deep ticket. Keep the units isolated so retries, evidence capture, and downstream unblocking can happen incrementally.
   - **Code ticket type rule:** If a ticket's primary work is implementing or modifying code, set `task_type: code_build` (not `build`).
   - **Cleanup ticket type rule:** For bounded non-code cleanup tickets, prefer `artifact_cleanup`, `receipt_cleanup`, or `docs_cleanup` instead of `general` using the same distinctions as Step 5 above. These are the narrow Gemini lanes and should only be used for low-risk cleanup work that does not change code or project strategy.
   - **Frontend design rule:** Carry forward `ui_work: true`, `design_mode`, and tag `ui-design` for any ticket that changes a user-facing UI surface. Carry forward `stitch_required: true` plus tag `stitch-required` only when the governing design mode is `stitch_required`.
   - Carry forward `public_surface: true` / tag `public-surface` for public-facing marketing surfaces, `existing_surface_redesign: true` / tag `existing-surface-redesign` when redesigning an already-existing user-facing surface, `page_contract_required: true` / tag `page-contract-required` for top-level nav surfaces, and `route_family_required: true` / tag `route-family-required` for governed operator-console routes.
   - Self-review, QC, and artifact-polish-review tickets governing the same surface must inherit the same UI metadata as the build/redesign ticket (`ui_work`, `design_mode`, `stitch_required`, `public_surface`, `existing_surface_redesign`, `page_contract_required`, `route_family_required`) so the runtime and gates stay strict end-to-end.
5. For complex tickets, set `complexity: deep`.
6. Update the plan with the new ticket IDs. For capability-waves, write them into both the active anchor phase and the active wave row. The orchestrator's loop will call this skill again when the current wave or phase needs re-planning.

### Step 5: Write Back

Update the plan file in place. Append to Plan History:
```
- {now}: {Phase {N} complete. Phase {N+1} active | Wave {X} re-planned inside Phase {N}} with {M} tickets. {brief summary of what changed}
```

## Architecture Decision Updates

If an executor discovers that an architecture decision needs to change mid-project:
1. The executor creates a decision record in the appropriate `decisions/` directory explaining why.
2. The orchestrator reads the decision record and triggers project-plan in update mode.
3. The plan's Architecture Decisions table is updated with the new choice, rationale, and date.
4. Any open tickets that depend on the changed decision are flagged for review.

## Error Handling

- If the project has `has_existing_codebase: true` but the bridge analyze fails, proceed with standard planning. Log the failure in Open Questions. The Phase 0 (Index & Analyze) ticket should still be created — indexing may succeed even if the pre-plan analyze call failed (e.g., transient error, missing dependency at plan time).
- If the goal is too vague to make architecture decisions, create a "Discovery" Phase 0 with tickets for research, prototyping, and decision-making. Phase 1 starts after Discovery completes.
- If phases cannot be clearly defined, default to: Phase 1 = Vertical Slice (one complete path through the core experience), Phase 2 = Full Feature Build, Phase 3 = Content/Polish, Phase 4 = Verification Manifest & Proof Execution (for code/software by default; other domains when mixed proof is needed), Phase 5 = Quality Assurance (self-review + QC), Phase 6 = Adversarial Stress Test (if triggered), Phase 7 = Artifact Polish Review, Phase 8 = Admin Usability Review, Phase 9 = Delivery. Every build phase (1-3) includes runtime verification at its gate — build compiles, launches, and prior-phase functionality still works (regression check). Tag all exit criteria with [EXECUTABLE], [INFRASTRUCTURE-DEPENDENT], or [MANUAL].
- **Capability-waves heuristic.** For frontier/high-novelty/admin-priority/extreme-scale/existing-codebase campaigns, default to `execution_model: capability-waves`. Use 3-5 anchor phases, a Capability Register, and a Dynamic Wave Log. Do not write a long detailed tactical phase script unless the path is genuinely stable and low-uncertainty.
- **Advance-grade heuristic.** For frontier/high-novelty/admin-priority/extreme-scale/existing-codebase campaigns, default every anchor phase that upgrades a core mission capability to `**Advance grade threshold:** A`. These campaigns exist to earn the claim, not to move on with "good enough." Lower the threshold only with explicit justification and only on non-core supporting phases.
- **No fake certainty rule.** If the real sequence depends on proof results, failed experiments, or architecture replacement, encode the stable part as anchor phases and the tactical part as waves. A neat 10-phase fiction is worse than an honest 4-phase campaign with dynamic wave re-planning.
- **Phase brief heuristics.** Mark `**Phase brief:** required` when a phase has a materially different proof or evaluator lens than the project brief alone can express cleanly. Common triggers:
  - verification / manifest execution phases
  - QA phases with specific media/evidence contracts
  - clean-room adversarial or compliance phases
  - artifact-polish / review-pack phases
  - delivery / handoff phases with packaging and review-surface rules
  For normal build phases that are still implementing the same core mission, prefer `none` unless the phase genuinely changes what good looks like.
- **Master project brief first.** A project-scoped creative brief is the root contract. Phase-scoped and ticket-scoped briefs are only valid as supplements. If a plan currently has a phase brief but no project brief, that is a planning defect: insert a project-scoped creative-brief ticket immediately, block downstream execution behind it, and treat the narrower brief as provisional until the master brief lands. Never create a brief cycle; the root project brief stays executable, and narrower briefs wait on it, not vice versa.
- If prior art exists but the project is frontier/high-novelty, default to `pattern_only` reuse. A strong archived project is not a substitute for first-principles architecture. Missing `## Playbook Usage Contract` or `## Why This Cannot Just Be The Playbook` on a frontier project is a planning failure.
- If an active frontier project has already built meaningful foundation code and later evidence shows the roadmap is too playbook-derived or otherwise mis-sequenced, do **not** default to a restart. Insert an **Architecture Delta Review** gate instead: architecture delta review → keep/change/replace matrix → scale-envelope/proof-program design → plan rebaseline. Freeze downstream build tickets behind the rebaseline ticket, retain the foundation unless explicitly rejected, and continue from the corrected roadmap.
- If the project is small (fewer than 10 tickets), use a simplified plan — but **every client work project must include the minimum quality pipeline regardless of size**: creative brief → build/execute → self-review → quality check → artifact polish review → deliver → **await client acceptance**. These can be in 1-2 phases but all steps must exist as tickets. Even a 10-minute task benefits from a brief and a QC pass. **Mandatory inline blocker:** after artifact polish review and before delivery, the orchestrator must run the credibility gate plus the pre-delivery review. **Exception:** Practice client projects (`is_practice: true`) follow the same pipeline but skip the deliver and await-client-acceptance tickets — the final gate review replaces client acceptance.
- **Adversarial stress test phase (complexity-triggered).** For complex or high-risk deliverables, add an independent stress test phase after QC and before artifact polish review/delivery. This is NOT the same as QC — QC verifies the deliverable meets the spec. The stress test tries to **break** it.

  **When to include stress testing (ANY ONE of these triggers is sufficient):**
  - The deliverable is a code tool, API, MCP, or system that processes user-provided or untrusted input
  - The deliverable will be pointed at real-world data the builder didn't control (client codebases, user uploads, external APIs)
  - The deliverable has autonomous behavior (makes decisions, modifies files, sends requests without human confirmation)
  - The project has 15+ build tickets or spans 3+ phases (complexity signal)
  - The creative brief's Enterprise Validation Plan identifies high-risk failure scenarios
  - Admin explicitly requests it
  - The deliverable's core value proposition involves correctness guarantees (e.g., "safe refactoring," "accurate analysis," "verified data")

  **When to skip (ALL must be true):**
  - The deliverable is static output (websites, PDFs, presentations, images, communication campaigns) AND
  - It does not process external input or make autonomous decisions AND
  - The project has fewer than 10 tickets

  **Precedence:** If ANY include trigger is met, stress testing is included — even if some skip conditions are also true. Include triggers always win. The skip criteria only apply when zero include triggers are met.

  **Stress test ticket chain:**
  The stress test is a mini-project within the project — 1-3 tickets depending on scope:

  1. **Stress test ticket** (`task_type: stress_test`, `complexity: deep`):
     - Assigned to a **fresh agent with no context** from the build phase. The agent reads ONLY the README, the creative brief, and the deliverable itself — not the build tickets, not the work logs, not the self-review notes. This forces a genuinely independent perspective.
     - The agent's job is adversarial: find bugs, edge cases, performance cliffs, security issues, and UX failures. Specifically:
       a. **Feed it bad input** — malformed files, empty files, enormous files, files in unsupported formats, files with encoding issues
       b. **Kill it mid-operation** — terminate the process at 50% and verify recovery/resume
       c. **Hit scale limits** — run it at 10x the expected scale and document where it degrades
       d. **Test every CLI command/API endpoint** with both valid and invalid arguments
       e. **Run the core value proposition end-to-end** — not just "does it start" but "does it actually do the thing it claims to do, correctly"
       f. **Check for the obvious** — phantom dependencies, hardcoded assumptions, commands that silently do nothing
     - Output: a stress test report documenting every finding with severity (blocker/major/minor), reproduction steps, and suggested fix.

  2. **Fix tickets** (if blockers/majors found) — created from the stress test report. Same revision pipeline: fix → self-review → QC → artifact polish review.

  3. The artifact-polish and delivery tickets are blocked by the stress test ticket (and any fix tickets). Nothing ships until stress testing passes.

  **Stress test verdict:**
  - **PASS** — no blockers, no majors. Minors documented in Known Limitations. Delivery may proceed.
  - **FAIL** — blockers or majors found. Fix tickets created. Stress test re-runs after fixes land. Delivery stays blocked.
  - **PASS with caveats** — no blockers. Majors exist but are genuine limitations (not fixable bugs). These must be disclosed to the client via the pre-delivery gap communication gate BEFORE delivery. The client must acknowledge the limitations before the delivery ticket unblocks. If the client rejects the caveats, create fix tickets and re-test. Delivery does NOT proceed on PASS with caveats until client acknowledgment.

  **This catches what QC misses.** QC asks "does it match the brief?" The stress test asks "what happens when a real user does something the brief didn't anticipate?" The Refactor Engine's core refactoring loop bug — where tests didn't actually test the refactored code — is exactly the kind of thing a stress test would catch in minutes by simply running the refactoring pipeline end-to-end and checking the output. (Learned from 2026-03-21: independent code review found a core functional bug that passed through self-review, QC, and the pre-delivery gate.)
- **Phase-level adversarial probes (MANDATORY for risky feature-heavy implementation phases).** Do NOT wait until the dedicated final stress phase to pressure-test every new risk surface. When a build phase introduces new trust-sensitive behavior, add one narrower clean-room probe pack to that phase after QC and before artifact polish / phase advancement.

  **When to include a phase-level adversarial probe (ANY ONE is enough):**
  - The phase introduces auth, permissions, credential vault, or other security boundary behavior
  - The phase introduces native runtime or permission-dependent behavior (Tauri, macOS permissions, launch/bootstrap, local file/runtime bindings)
  - The phase introduces governed writes, mutation flows, approvals, comments/corrections, or canonical-state changes
  - The phase introduces ingest/parse/upload behavior (knowledge dump uploads, YAML/frontmatter parsing, artifact ingestion, corrupt-input handling)
  - The phase introduces retrieval, memory, sync, storage, indexing, or contradiction-handling behavior
  - The phase introduces integrations, tool access, runtime adapters, or external API dependency behavior
  - The phase introduces live-watch, artifacts/evidence, media, or preview surfaces that can break under missing/oversized/bad assets

  **When to skip:**
  - The phase is already the dedicated full adversarial stress-test phase, OR
  - The phase is primarily review/polish/usability/delivery work and does not introduce new risky implementation behavior

  **What to add to the plan when required:**
  - One exit criterion: `Phase-level adversarial probe pack PASS (zero blockers, zero majors) [EXECUTABLE] [TRACES: ...]`
  - One clean-room probe ticket placeholder after QC and before artifact polish / phase advancement:
    - `Adversarial probe pack — {phase risk families}` (`task_type: adversarial_probe`, `complexity: normal|deep`)
  - The phase brief should define the probe pack explicitly when possible: risk families, bad-input / degraded-state probes, pass threshold, and gate impact

  **Important:** this is not a mini copy of the full 61-scenario stress ritual. It is a tight pack aimed at the new phase risk surface only. The final broad stress phase still exists for near-ship trust. The point here is earlier, cheaper skepticism — not maximum suffering every time.
- **Batch work must be split into atomic tickets.** When a task involves processing multiple independent units (states, files, records, pages, assets), create ONE ticket per unit — not one ticket for the whole batch. Each unit should complete independently within the 30-minute timeout. This prevents timeout kills from losing work: if CA completes and NY gets killed, CA's output is saved and NY restarts next cycle. Examples:
  - Data extraction across 5 states → 5 tickets (one per state)
  - Processing 10 client files → 10 tickets (one per file)
  - Building 8 game regions → 8 tickets (one per region)
  - Generating reports for 4 clients → 4 tickets (one per client)
  - Re-indexing 6 repos or 6 shards → 6 tickets (one per repo/shard) + 1 aggregate report ticket
  Each unit ticket should name its expected output file and check if it already exists before starting (idempotent). Never put multiple independent units in one ticket unless they complete in under 10 minutes total.
  **Scaling:** For large batches (10+ units), use phased fan-out/fan-in: split into batches of 5-10 units per phase. Each phase has per-unit execution tickets, then ONE batch-level self-review + QC + delivery. Don't create 50 separate full-pipeline chains — fan out the execution, fan in the quality checks.
  **Deep-run exception handling:** If an independent unit is itself long-running (for example, full-repo indexing that may take hours), that is even more reason to keep it isolated as its own deep ticket. Do not combine several multi-hour independent units into one critical-path ticket unless serialization is explicitly required and documented.
- **Mid-project change control must be explicit.** If new work arrives after the project is already underway, do not just drop it into the ticket graph informally. Use [[project-change-control]] to classify the request as a `minor_ticket_delta`, `phase_amendment`, `project_replan`, or `pivot`. Small deltas can become tickets directly; anything that changes acceptance criteria, proof shape, or phase architecture must amend the phase brief or project plan first.
- **The "await client acceptance" ticket** is always the LAST ticket in the pipeline for real clients. **Practice client projects skip this ticket entirely** — the final gate review replaces client acceptance. For real clients: it has status `waiting`, assignee `human`, and is blocked by the delivery ticket. The delivery handoff asks the client/operator to reply APPROVE or request changes. When the response is supplied to the vault:
  - **APPROVE:** the acceptance ticket closes. Optional rating requests are operator-mediated and non-blocking. Project completes.
  - **Changes requested:** create revision feedback tickets manually or from the operator-provided request artifact. Acceptance ticket is re-blocked on the new re-delivery ticket (status: `blocked`, `blocked_by` updated). Fix tickets are created with the **revision quality pipeline** — revisions are held to the same standard as the original delivery. The minimum revision pipeline is: fix ticket(s) → self-review ticket → QC ticket → artifact polish review ticket → re-delivery ticket. The QC and artifact-polish tickets must pass, and the re-delivery must go through the credibility gate and pre-delivery gate (same A-grade requirement as the original delivery). The re-delivery handoff must include the APPROVE request **and** an explicit review surface ("review here") that points to the updated client-accessible repo/build/link. For code/mobile deliverables, the canonical review surface from the original delivery must be updated before the re-delivery handoff is prepared. Acceptance awaits again after re-delivery. Skipping self-review, QC, artifact polish review, either pre-delivery gate, or the review-surface update on revision work is a process violation — "it's just a small fix" is not an excuse to bypass quality checks.
  - **No response after 72h:** one reminder sent. After 144h total: auto-close as accepted. **Timer resets on each revision cycle:** when a revision is triggered, the acceptance ticket is re-blocked on the new re-delivery ticket (status: `blocked`). This suspends the 72h/144h clock. When the re-delivery ticket closes, the orchestrator auto-unblocks the acceptance ticket back to `waiting` and the clock restarts from that moment — counting from the latest re-delivery, not the original.
  - **Rating** is always optional and never blocks project closure. If the client rates, it's saved to their preferences. If not, no follow-up.

## Research-Context Principles

- Research-context informs architecture; it does not replace proof.
- A research-context claim does not authorize unavailable tooling or vendor capability in this run.
- Do not bloat the plan with raw research. Import only claim IDs and implications that change architecture, phases, risks, assumptions, or proof.
- Low-confidence claims must be tracked as assumptions or open questions with validation methods.
- Deprecated-pattern findings should influence anti-patterns, migration choices, and planning risks.

## See Also

- [[orchestrator]]
- [[create-project]]
- [[create-ticket]]
- [[sync-context]]
- [[gather-context]]
- [[creative-brief]]
