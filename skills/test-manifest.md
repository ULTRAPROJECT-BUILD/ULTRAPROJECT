---
type: skill
name: test-manifest
description: Legacy skill name for the verification-manifest workflow. Generates an exhaustive proof manifest from the creative brief and source code, then executes every EXECUTABLE item against the running deliverable. Produces a pass/fail report with proof-type classification, screenshot evidence, and failure classification.
inputs:
  - project (required — project slug)
  - client (optional — client slug)
  - mode (required — "generate" or "execute")
  - brief_path (required — creative brief to derive tests from)
  - deliverables_path (required for execute mode)
  - manifest_path (required for execute mode — path to the generated manifest)
---

# Verification Manifest

This skill keeps the historical file name `test-manifest`, but the canonical concept is a **verification manifest**.

You are generating or executing an exhaustive verification manifest for a deliverable. The manifest is the contract between "what the brief promises" and "what actually works." It is **derived from** the creative brief — not a parallel spec.

The key rule: **not every proof item is a test**. The manifest may contain automated tests, build checks, runtime proofs, inspection checks, artifact checks, external validations, and manual-review items.

## When to Use

- **Generate mode:** After the creative brief is finalized and before or during the build phase. The manifest becomes the verification contract.
- **Execute mode:** After all build tickets for a phase close. Execute the manifest against the running deliverable, classify failures, and produce a results report.

---

## Generate Mode

### Step 1: Read the Sources

Read all of the following:
1. The creative brief — especially acceptance criteria, verification protocol, and critical flows
2. The project plan — exit criteria for the current phase
3. The source code (if it exists yet):
   - Component file list (`src/components/**`, `src/features/**`, etc.)
   - Route definitions / navigation structure
   - Feature flags or capability declarations
   - UI entry points (App.tsx, main layout, sidebar items, tab registrations)

**The manifest must cover everything in the brief's acceptance criteria.** Source code discovery adds items the brief may not enumerate (e.g., a settings panel that exists in code but isn't mentioned in the brief).

### Step 2: Build the Manifest

For each acceptance criterion or user-facing claim that needs proof, create a manifest item in this format:

```markdown
| ID | Category | Proof Type | Criterion IDs | Element | Action | Expected Result | Pass Criteria | Priority | Executability |
```

**Categories:**
- `navigation` — every tab, sidebar item, menu item, breadcrumb, route
- `form` — every input field (test valid, invalid, empty, and boundary inputs)
- `button` — every button with its expected action and result
- `panel` — every view/panel with expected content when active
- `error` — every way the user can trigger an error (invalid input, network failure, empty state)
- `flow` — multi-step end-to-end workflows (e.g., "connect → query → export")
- `data` — data display correctness (grid renders rows, chart shows values, counts match)

**Proof types (MANDATORY):**
- `automated_test` — assertion-backed unit, integration, contract, or E2E test
- `build_check` — build, typecheck, lint, dependency audit, packaging, schema/codegen
- `runtime_proof` — a running user flow or live interaction in the target runtime
- `inspection_check` — code/config/source inspection, grep, route inventory, static verification
- `artifact_check` — deliverable/supporting-artifact presence and correctness (README, deployment docs, LIMITATIONS, screenshots, exports)
- `external_validation` — comparison against an external truth source (ground truth, citation/source checks, schema authority, benchmark target)
- `manual_review` — requires human judgment or sensory access (screen reader, visual taste, UX feel)

**Priority assignment:**
- `P0` — items from the brief's "critical flows" section + any item on the primary user journey. Blocks delivery.
- `P1` — all other acceptance criteria items. Blocks delivery if EXECUTABLE.
- `P2` — edge cases, polish, items not in acceptance criteria. Documented if broken, does not block.

**Executability classification:**
- `EXECUTABLE` — can be tested right now with available tools and environment
- `INFRASTRUCTURE-DEPENDENT` — requires external service, database, hardware, or display server not guaranteed in the build environment. **Must define fallback evidence** (e.g., "unit tests cover this code path" or "Tauri IPC mock verifies the handler").
- `MANUAL` — requires human judgment (visual taste, UX feel, accessibility with screen reader). Deferred to admin usability review.

### Step 3: Apply Token Budget Controls

- **Max 80 items per manifest.** If the deliverable requires more, split across phases or batch related items.
- **Batch related items** into single entries: e.g., "Navigate to each sidebar tab (Connections, Explorer, Query, ERD, History, Saved)" = 1 item covering 6 tabs, not 6 separate items.
- **Max 2 screenshots per item** during execution (before + after action).
- If the brief has >80 verifiable criteria, prioritize: all P0 items first, then P1 up to the cap, then summarize remaining P1/P2 as batch items.

### Step 4: Save the Manifest

Save to `{snapshots_path}/{date}-verification-manifest-{project}.md` with this structure. Legacy projects may continue using `*-test-manifest-*`, but new work should prefer `verification-manifest`.

```markdown
# Verification Manifest — {project}

**Generated:** {timestamp}
**Brief:** {brief_path}
**Total items:** {count} ({P0_count} P0, {P1_count} P1, {P2_count} P2)
**Executable:** {executable_count} | **Infra-dependent:** {infra_count} | **Manual:** {manual_count}

## P0 — Critical Flows

| ID | Category | Proof Type | Criterion IDs | Element | Action | Expected Result | Pass Criteria | Executability |
|----|----------|------------|---------------|---------|--------|-----------------|---------------|---------------|
| VM-001 | flow | runtime_proof | AC-01, AC-04 | Connect + query | ... | ... | ... | EXECUTABLE |

## P1 — Acceptance Criteria

| ID | Category | Proof Type | Criterion IDs | Element | Action | Expected Result | Pass Criteria | Executability |
|----|----------|------------|---------------|---------|--------|-----------------|---------------|---------------|

## P2 — Polish & Edge Cases

| ID | Category | Proof Type | Criterion IDs | Element | Action | Expected Result | Pass Criteria | Executability |
|----|----------|------------|---------------|---------|--------|-----------------|---------------|---------------|

## Proof Matrix

| Proof Type | Item Count | Purpose |
|-----------|------------|---------|
| automated_test | {n} | Assertion-backed verification |
| build_check | {n} | Build/type/lint/audit/package proof |
| runtime_proof | {n} | Running user/system behavior |
| inspection_check | {n} | Static verification via source/config inspection |
| artifact_check | {n} | Deliverable/support artifact integrity |
| external_validation | {n} | Comparison against external truth |
| manual_review | {n} | Human judgment-only checks |

## Infrastructure-Dependent Items (fallback evidence required)

| ID | Element | Why Infra-Dependent | Fallback Evidence |
|----|---------|---------------------|-------------------|

## Manual Items (deferred to admin review)

| ID | Element | What to Check | Deferred To |
|----|---------|---------------|-------------|
```

---

## Execute Mode

### Step 1: Launch the Deliverable

Determine the deliverable type and launch it:

| Deliverable Type | Launch Command | Primary Test Tool | Fallback Tool |
|-----------------|----------------|-------------------|---------------|
| Web app (Vite/Next/etc.) | `npm run dev` or `npm run preview` | agent-browser | Playwright Python API |
| Desktop app (Tauri) | `open {app_path}` or `npm run tauri dev` | Computer Use MCP | None |
| Desktop app (Electron) | `npm start` or `open {app_path}` | Computer Use MCP | None |
| CLI tool | Direct execution via Bash | Bash | N/A |
| API / MCP server | Start server process | curl / Python requests | N/A |
| Mobile (web-based) | `npm run dev` + agent-browser mobile viewport | agent-browser `-p ios` | N/A |

Wait for the application to be ready before starting tests.

### Step 2: Execute EXECUTABLE Items

Process items in priority order: all P0 first, then P1, then P2.

For each EXECUTABLE item:

1. **Locate the element** — take a screenshot, identify the target element in the current state. For agent-browser: use `snapshot -i` to find interactive elements. For Computer Use: use `screenshot` and identify coordinates.
2. **Perform the action** — click, type, navigate, submit, etc.
3. **Wait for result** — allow time for async operations (network, animations, state changes).
4. **Screenshot the result** — capture the after-state.
5. **Evaluate pass/fail** — compare the actual result against the pass criteria.
6. **Classify failures:**
   - `PASS` — result matches criteria
   - `CODE_DEFECT` — the product is broken (button doesn't work, panel doesn't load, error not shown, wrong data displayed). **Routes to Codex fix ticket.**
   - `INFRA_MISSING` — the test can't run because the environment lacks a required service (database not running, API key missing, display server unavailable). **Reclassify item as INFRASTRUCTURE-DEPENDENT.**
   - `HARNESS_FLAKY` — the test tool failed (screenshot timeout, element not found but likely a tool issue not a product issue). **Retry once with the fallback tool. If still fails, skip with evidence.**
   - `SPEC_AMBIGUOUS` — the expected behavior is unclear from the brief (two valid interpretations). **Escalate to admin.**

### Step 3: Produce Results Report

Save to `{snapshots_path}/{date}-verification-results-{project}.md`. Legacy projects may continue using `*-test-manifest-results-*`, but new work should prefer `verification-results`.

```markdown
# Verification Results — {project}

**Executed:** {timestamp}
**Manifest:** {manifest_path}
**Deliverable:** {deliverables_path}

## Summary

| Metric | Count |
|--------|-------|
| Total items | {total} |
| Executed (EXECUTABLE) | {executed} |
| Skipped (INFRA-DEPENDENT) | {infra_skipped} |
| Skipped (MANUAL) | {manual_skipped} |
| **PASS** | {pass_count} |
| **CODE_DEFECT** | {defect_count} |
| **INFRA_MISSING** | {infra_missing_count} |
| **HARNESS_FLAKY** | {flaky_count} |
| **SPEC_AMBIGUOUS** | {ambiguous_count} |

**EXECUTABLE P0 pass rate:** {p0_pass}/{p0_total} ({p0_pct}%)
**EXECUTABLE P1 pass rate:** {p1_pass}/{p1_total} ({p1_pct}%)
**EXECUTABLE P2 pass rate:** {p2_pass}/{p2_total} ({p2_pct}%)

## Proof Summary

| Proof Type | Total | PASS | Non-PASS |
|-----------|-------|------|----------|
| automated_test | {count} | {pass} | {non_pass} |
| build_check | {count} | {pass} | {non_pass} |
| runtime_proof | {count} | {pass} | {non_pass} |
| inspection_check | {count} | {pass} | {non_pass} |
| artifact_check | {count} | {pass} | {non_pass} |
| external_validation | {count} | {pass} | {non_pass} |
| manual_review | {count} | {pass} | {non_pass} |

## CODE_DEFECT Failures (route to Codex)

| ID | Element | Action | Expected | Actual | Screenshot | Notes |
|----|---------|--------|----------|--------|------------|-------|

## INFRA_MISSING (reclassified)

| ID | Element | Missing Infrastructure | Fallback Evidence |
|----|---------|----------------------|-------------------|

## HARNESS_FLAKY (skipped with evidence)

| ID | Element | Tool Used | Error | Retried? | Screenshot |
|----|---------|-----------|-------|----------|------------|

## SPEC_AMBIGUOUS (escalate to admin)

| ID | Element | Ambiguity | Options |
|----|---------|-----------|---------|

## Full Results

| ID | Proof Type | Criterion IDs | Element | Action | Result | Classification | Screenshot |
|----|------------|---------------|---------|--------|--------|----------------|------------|
```

---

## Integration with Orchestrator

The orchestrator's Build-Prove-Fix Loop consumes the results report:
- `CODE_DEFECT` items → create Codex fix tickets with the screenshot and expected/actual from the report
- After Codex fixes → re-execute only the failed items + 20% regression sample of passing items
- Loop until 100% EXECUTABLE P0 + 100% EXECUTABLE P1 pass
- Safety valve: 5 iterations max, then escalate to admin

## See Also

- [[creative-brief]] — source of acceptance criteria and verification protocol
- [[quality-check]] — consumes manifest results as a gate
- [[orchestrator]] — runs the Build-Prove-Fix Loop
- [[deliverable-standards]] — defines enterprise quality baselines
- [[project-plan]] — criterion classification at planning time
