---
type: skill
name: consolidate-aesthetics
description: Closed-loop preset evolution. Reads outcome telemetry across recent projects, runs aesthetic_change_proposer for each preset that crossed the proposal threshold, manages promising-but-insufficient queue for low-data signals, deprecates underperforming presets. Runs autonomously per cadence; generates proposals; operator approves on their schedule.
inputs:
  - cadence (required: scheduled|on_demand)
  - preset_filter (optional: only consolidate this preset; default = all)
  - dry_run (optional: detect proposals without writing them)
---

# Consolidate Aesthetics Skill

## Mission

Run the closed-loop telemetry pass for the Visual Specification System.

This skill is a post-delivery consolidator. It does not interrupt active
projects, does not ask the operator for confirmation during its normal run, and
does not mutate active presets directly. Its job is to read outcome telemetry,
generate evidence-backed preset-update proposals, route underpowered but useful
signals into the promising queue, flag presets that may need redesign or
deprecation, and surface a concise operator report.

Default behavior is autonomous:

- Scheduled cadence runs after every Nth completed VS-eligible project for each
  preset. N defaults to 3 unless platform config declares a different value.
- On-demand cadence runs immediately over the same corpus.
- Operator approval happens later by reviewing proposal artifacts already
  written under `vault/archive/visual-aesthetics/proposals/`.
- A dry run computes the same decisions and writes only the summary report
  marked `dry_run: true`; it does not create proposal artifacts.

The skill is deliberately high precision. Preset defaults change only when
outcome evidence, cohort controls, tag audit, holdout validation, and regression
replay all support the change. Sparse positive signals are preserved, but they
do not contaminate global defaults.

## Inputs

Required:

- `cadence`: `scheduled` or `on_demand`.

Optional:

- `preset_filter`: preset slug to consolidate. If omitted, consolidate every
  preset that appears in the outcome corpus or in
  `vault/archive/visual-aesthetics/presets/`.
- `dry_run`: truthy value means detect and report without writing proposal
  artifacts.

Resolve the machine-local date before writing any report:

```bash
date +%Y-%m-%d
date +"%Y-%m-%dT%H:%M"
```

Use the local timestamp in markdown reports. Helper scripts may emit UTC
timestamps in JSON when their schemas require it; do not rewrite those helper
outputs by hand.

## Cadence Rules

Scheduled runs are eligible when any of these are true:

- A preset has accumulated at least 3 new delivered outcomes since its last
  consolidation report.
- A preset has accumulated at least 5 total outcomes inside the corpus window.
- A prior promising signal for the preset exists and the preset has new outcome
  data since that signal was written.
- A monthly operator engagement report has not been generated for the current
  month.

On-demand runs ignore Nth-project gating and evaluate the requested preset or
all presets immediately.

Never block delivery on this skill. If a script fails, capture the failure in
the consolidation report and continue with the next preset.

## Working Paths

Repository-relative paths:

- Outcome corpus root: `vault/snapshots/`
- Preset directory: `vault/archive/visual-aesthetics/presets/`
- Medium plugin directory: `vault/archive/visual-aesthetics/mediums/`
- Proposal directory: `vault/archive/visual-aesthetics/proposals/`
- Promising signal directory:
  `vault/archive/visual-aesthetics/proposals/_promising-but-insufficient/`
- Regression reports:
  `vault/archive/visual-aesthetics/proposals/reports/`
- Summary reports: `vault/config/aesthetic-consolidation-{date}.md`
- Monthly engagement reports:
  `vault/config/visual-system-engagement-{YYYY-MM}.md`
- Waiver log: `vault/config/visual-spec-waivers.md`
- Platform config: `vault/config/platform.md`

The helper scripts already know their default output paths. Prefer their
defaults unless this skill is in `dry_run` mode or a fixture explicitly supplies
temporary paths.

## Step 1 — Resolve outcome corpus

Walk all visual outcome artifacts from the recent corpus window.

Default window:

- 90 days ending at the current local date.

File pattern:

```text
vault/snapshots/*/visual-spec-outcome-*.json
vault/clients/*/snapshots/**/visual-spec-outcome-*.json
```

Use `vault/snapshots/` as the default `--outcomes-dir` for the helper scripts,
because `visual_spec_telemetry_common.load_outcomes_with_metadata()` walks
recursively. Include client-scoped snapshots in the summary by explicitly
checking both roots when reporting corpus coverage.

For each valid outcome, record:

- `project`
- `client_id`
- `client_organization_id`
- `client_domain`
- `visual_quality_target_medium`
- `visual_quality_target_preset`
- `visual_axes`
- `preset_default_overrides`
- `visual_gate_first_attempt`
- `visual_gate_final`
- `visual_gate_revision_rounds`
- `reviewer_grades`
- `operator_acceptance`
- `revision_count_during_build`
- `delivery_review_grade`
- `build_duration_hours`
- `vs_phase_duration_hours`
- source path
- inferred timestamp

Group outcomes by `visual_quality_target_preset`.

If an outcome fails schema validation, do not stop the run. Add it to the
summary report under `Invalid outcome artifacts` with the source path and helper
error payload. Invalid outcomes are excluded from proposal generation.

Use this command to collect a month-level operator engagement report as
supporting context:

```bash
python3 scripts/aggregate_visual_engagement_report.py \
  --month "$(date +%Y-%m)" \
  --json-out "vault/config/visual-system-engagement-$(date +%Y-%m).json"
```

If the engagement command fails, record the failure and continue. Proposal
generation does not require the monthly report.

Build or refresh the brief-contract collusion baseline when the corpus has at
least five historical projects, and at least monthly during scheduled cadence:

```bash
python3 scripts/build_collusion_baseline.py \
  --out vault/config/brief-contract-collusion-baseline.json
```

If the helper reports `insufficient_samples`, record that cold-start state in
the consolidation report and leave any existing baseline untouched.

## Step 2 — Per-preset proposal generation

Resolve the preset list:

1. If `preset_filter` is set, evaluate only that preset.
2. Otherwise include every preset file in
   `vault/archive/visual-aesthetics/presets/*.md`.
3. Add any preset-like value found in outcome data, including custom labels, so
   missing preset files are visible in the report.

For each preset with 5 or more valid outcomes, run:

```bash
python3 scripts/aesthetic_change_proposer.py \
  --outcomes-dir vault/snapshots \
  --preset "{preset}" \
  --json-out "vault/archive/visual-aesthetics/proposals/reports/{preset}-proposal-run-{date}.json"
```

The proposer performs the core controls:

- Same-direction `aesthetic-default-wrong` override clustering.
- Minimum project threshold.
- Distinct organization threshold.
- Domain concentration threshold.
- Reviewer diversity threshold.
- Reviewer/operator coupling check.
- Delivery grade effect-size threshold.
- Revision reduction threshold.
- Operator acceptance threshold.
- Holdout split and validation.
- Tag audit orchestration.
- Medium-aware regression replay orchestration.
- Proposal markdown creation when all hard controls pass.
- Promising signal creation when the signal is positive but underpowered.

For presets with 2 to 4 outcomes showing positive direction, run the proposer
too. The proposer will route valid low-data signals to:

```text
vault/archive/visual-aesthetics/proposals/_promising-but-insufficient/
```

Promising-but-insufficient criteria:

- At least 2 projects observed.
- Direction is consistent.
- Positive outcome indicator exists:
  - delivery grade delta is positive, or
  - revision reduction is positive, or
  - operator acceptance is no worse than baseline while another metric
    improves.
- Evidence is below the auto-proposal threshold.

If `dry_run` is true, do not let helper defaults write proposal markdown. Run the
proposer with a temporary `--out` path in the OS temp directory and record the
JSON verdict only. Delete the temporary markdown after reading it. Do not delete
any pre-existing proposal files.

## Step 3 — Tag audit per proposal

For each preset that produced a proposal, promising signal, or non-empty
candidate list, run an explicit tag audit unless the proposer JSON already
includes a fresh audit payload from the same run.

Command:

```bash
python3 scripts/audit_override_tags.py \
  --outcomes-dir vault/snapshots \
  --preset "{preset}" \
  --llm-mode "${VISUAL_TELEMETRY_AUDIT_LLM_MODE:-stub}" \
  --json-out "vault/archive/visual-aesthetics/proposals/reports/{preset}-tag-audit-{date}.json"
```

Expected pass conditions:

- `verdict` is `pass` or `no_data_yet`.
- Average confidence is at least the platform threshold, normally `0.8`.
- Disagreement rate is below 30 percent.
- Invalid tags are either empty or explicitly routed to manual review.

If the audit fails, proposals remain written but must stay
`operator_decision: pending` and the consolidation report must mark the preset
`manual_tag_audit_review`. Do not edit the proposal to approve, reject, or
supersede it.

## Step 4 — Regression replay per proposal

For each generated proposal, confirm the regression replay result.

The proposer usually calls `preset_regression_check.py` and embeds a regression
report path in proposal frontmatter. Verify that path exists and that its
payload is consistent with the proposal:

- `regression_check.status` matches the report's `regression_status`.
- `regression_check.method` is `real_rendering`, `simulate_only`, or
  `manual_review`.
- `regression_check.report_path` is repository-relative.
- Unsupported mediums use `operator_review_required`, not a silent pass.

If a proposal is missing a regression report, run replay manually:

```bash
python3 scripts/preset_regression_check.py \
  --proposed-change "{axis_or_token}={proposed_value}" \
  --preset "{preset}" \
  --historical-vs-dir vault/snapshots \
  --medium-plugin "vault/archive/visual-aesthetics/mediums/{medium}.md" \
  --json-out "vault/archive/visual-aesthetics/proposals/reports/{preset}-{axis_or_token}-regression-{date}.json"
```

Medium handling:

- `web_ui`, `presentation`, `document_typography`, and `data_visualization`
  should run deterministic replay when the mutation is supported.
- `native_ui` and `game_ui` may be partial and can return
  `operator_review_required`.
- `brand_identity`, `video_animation`, and `3d_render` are normally
  operator-review mediums unless their source artifact bundle provides a
  declared deterministic replay contract.

If regression replay returns `fail`, the consolidation report marks the
proposal blocked. Leave the proposal artifact intact so the evidence remains
auditable.

## Step 5 — Cohort + effect-size + holdout checks

These checks are already implemented inside
`scripts/aesthetic_change_proposer.py`; this skill verifies that the proposer
output contains the evidence before surfacing proposals as actionable.

Required verification fields:

- `cohort_pass`
- `effect_pass`
- `holdout_pass`
- `proposal_frontmatter.cohort_check.distinct_clients`
- `proposal_frontmatter.cohort_check.distinct_organizations`
- `proposal_frontmatter.cohort_check.distinct_domains`
- `proposal_frontmatter.cohort_check.reviewer_diversity_pass`
- `proposal_frontmatter.cohort_check.holdout_validation_pass`
- `proposal_frontmatter.outcome_delta.revision_count_delta`
- `proposal_frontmatter.outcome_delta.operator_acceptance_delta_pct`
- `proposal_frontmatter.outcome_delta.delivery_grade_delta`

Minimum quality thresholds come from `vault/config/platform.md`:

- `visual_spec_aesthetic_proposal_min_projects`: default `5`
- `visual_spec_telemetry_distinct_organizations_min`: default `3`
- `visual_spec_telemetry_max_domain_concentration_pct`: default `50`
- `visual_spec_telemetry_max_reviewer_concentration_pct`: default `40`
- `visual_spec_telemetry_min_effect_size_grade_points`: default `0.5`
- `visual_spec_telemetry_min_revision_reduction_pct`: default `30`
- `visual_spec_telemetry_min_operator_acceptance_pct`: default `80`
- `visual_spec_telemetry_holdout_min_projects`: default `3`
- `visual_spec_telemetry_reviewer_operator_coupling_max_pct`: default `60`

If the proposer output omits any required verification field, treat the run as
`error_incomplete_evidence` and do not promote the proposal in the summary.

## Step 6 — Deprecation review

Evaluate every preset with at least 10 valid outcomes in the corpus.

Compute:

```text
first_attempt_pass_rate =
  count(visual_gate_first_attempt == "PASS") / count(outcomes_for_preset)
```

If the rate is below 20 percent, write a deprecation or redesign proposal:

```text
vault/archive/visual-aesthetics/proposals/{preset}-{date}-deprecation-review.md
```

Use frontmatter:

```yaml
---
type: preset-deprecation-review
preset: "{preset}"
outcomes_evaluated: 10
visual_gate_first_attempt_pass_rate_pct: 15.0
threshold_pct: 20.0
status: redesign_or_deprecate_recommended
operator_decision: pending
created_local: "YYYY-MM-DDTHH:MM"
---
```

Body sections:

- `# Deprecation Review — {preset}`
- `## Evidence`
- `## Likely Causes`
- `## Options`
- `## Recommended Action`
- `## Operator Decision Log`

Do not delete or edit the preset. Deprecation requires an explicit later
operator decision because existing locked VS artifacts remain valid against
their original preset versions.

If `dry_run` is true, include the deprecation recommendation only in the summary
report and do not write the deprecation review artifact.

## Step 7 — Surface to operator

Write the summary report:

```text
vault/config/aesthetic-consolidation-{date}.md
```

The report is the only operator-facing artifact this skill must create every
run. It should be short enough to scan, but complete enough to audit.

Required report structure:

```markdown
---
type: aesthetic-consolidation-report
date: YYYY-MM-DD
generated_local: YYYY-MM-DDTHH:MM
cadence: scheduled|on_demand
preset_filter: all|{preset}
dry_run: true|false
---

# Aesthetic Consolidation — YYYY-MM-DD

## Run Summary
## Corpus
## Proposals Written
## Promising Signals
## Deprecation Reviews
## Audit and Regression Status
## Waiver and Unsupported-Medium Governance
## Invalid or Missing Data
## Next Operator Review Queue
```

Each proposal lands in:

```text
vault/archive/visual-aesthetics/proposals/
```

Each low-data promising signal lands in:

```text
vault/archive/visual-aesthetics/proposals/_promising-but-insufficient/
```

The operator reviews these artifacts on their schedule. Do not ask for
confirmation in the consolidation run.

## Governance Checks

Before finalizing the report, run governance helpers when their source logs
exist.

Operator waiver rate:

```bash
python3 scripts/check_operator_waiver_rate.py \
  --waiver-log vault/config/visual-spec-waivers.md \
  --operator-id "{operator_or_all}" \
  --json-out "vault/archive/visual-aesthetics/proposals/reports/waiver-rate-{date}.json"
```

Unsupported-medium approval rate:

```bash
python3 scripts/check_unsupported_medium_approval_rate.py \
  --proposals-dir vault/archive/visual-aesthetics/proposals \
  --operator-id "{operator_or_all}" \
  --json-out "vault/archive/visual-aesthetics/proposals/reports/unsupported-medium-approval-rate-{date}.json"
```

If the helper CLIs differ, run `--help` and adapt to the implemented argument
names. The report must still include the governance status:

- `green`: below threshold.
- `yellow`: 30-day waiver rate crossed warning threshold.
- `red`: waiver or unsupported-medium approval threshold requires second review
  or cooling-off before the next approval.
- `not_available`: source log does not exist yet.

Governance alerts do not block this skill; they block future waiver or
unsupported-medium approval flows through their gates.

## Failure Handling

Continue preset-by-preset.

For each failure, capture:

- preset
- command
- exit code when available
- stderr summary
- output path if any partial artifact was written
- recommended follow-up

Never delete partial proposal artifacts created by helper scripts. Mark them in
the summary as `needs_manual_cleanup_or_review` if they are incomplete.

If no outcome data exists, write a valid summary report with:

- corpus size `0`
- proposals `none`
- promising signals `none`
- deprecation reviews `none`
- next action `await_delivered_projects`

## Outputs

Always:

- `vault/config/aesthetic-consolidation-{date}.md`

When data exists:

- `vault/config/visual-system-engagement-{YYYY-MM}.md`
- `vault/config/visual-system-engagement-{YYYY-MM}.json`
- `vault/archive/visual-aesthetics/proposals/reports/{preset}-proposal-run-{date}.json`
- `vault/archive/visual-aesthetics/proposals/reports/{preset}-tag-audit-{date}.json`
- `vault/archive/visual-aesthetics/proposals/reports/*-regression.json`

When evidence passes:

- `vault/archive/visual-aesthetics/proposals/{preset}-{date}-proposal.md`

When evidence is positive but underpowered:

- `vault/archive/visual-aesthetics/proposals/_promising-but-insufficient/{preset}-{date}-promising.md`

When a preset underperforms:

- `vault/archive/visual-aesthetics/proposals/{preset}-{date}-deprecation-review.md`

Dry-run exception:

- Only the summary report and temporary JSON diagnostics are allowed to remain.

## Completion Criteria

The skill is complete when:

- Every eligible preset has been evaluated or explicitly skipped with reason.
- Tag audit and regression status are recorded for each proposal candidate.
- Promising low-data signals are preserved separately from auto proposals.
- Deprecation candidates are surfaced without mutating presets.
- The summary report names every artifact written.
- No active project or build ticket is blocked by this consolidation pass.
