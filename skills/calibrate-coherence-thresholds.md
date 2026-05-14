---
type: skill
name: calibrate-coherence-thresholds
description: Tune `vault/config/artifact-coherence-thresholds.yml` per medium/preset based on reviewer agreement, operator acceptance, and revision rate from past projects. Produces proposals for operator review on cadence; does not auto-apply changes.
inputs:
  - cadence (required: scheduled|on_demand)
  - medium_filter (optional)
  - preset_filter (optional)
  - dry_run (optional)
---

# Calibrate Coherence Thresholds

## Mission

Tune the quantitative artifact-coherence thresholds from observed outcomes without weakening the visual gate by accident.

This skill proposes changes only. It must not edit `vault/config/artifact-coherence-thresholds.yml` unless the operator explicitly approves the proposal in a separate instruction. The normal output is a proposal markdown file under:

`vault/archive/visual-aesthetics/proposals/coherence-threshold-{date}-proposal.md`

Use the machine-local clock for `{date}` and for any timestamps written to vault records:

```bash
date +"%Y-%m-%dT%H:%M"
```

Respect deterministic threshold precedence when analyzing or proposing any value:

`defaults -> per_medium_overrides -> per_preset_overrides`

## Step 1 — Resolve outcome corpus

Collect completed project evidence with enough data to compare quantitative verdicts against human and operator outcomes.

Primary inputs:

- `coherence_signoff` blocks in Visual Specification frontmatter
- JSON reports from `scripts/check_artifact_coherence.py`
- project outcome records under `vault/clients/*/projects/`, snapshots, decisions, and post-delivery reviews
- operator acceptance or revision notes from `post_delivery_operator_acceptance`
- revision counts during build, especially visual rework after coherence review

Apply filters before analysis:

- `medium_filter`: include only records whose VS medium matches
- `preset_filter`: include only records whose VS preset matches
- ignore records without both a quantitative verdict and a reviewer/operator outcome

For each eligible project, extract:

- project/client identifiers
- medium and preset
- threshold registry version applied
- effective threshold values after precedence resolution
- every quantitative check value and verdict
- reviewer signoff verdict
- reviewer qualitative disagreement notes
- operator acceptance or rejection
- number of visual revisions after signoff

If fewer than 5 eligible records exist for the selected scope, still write a proposal file, but mark it `sample_size_status: insufficient` and recommend no threshold changes.

## Step 2 — Per-threshold false-pass / false-fail rate computation

For each threshold, compare the quantitative verdict against the downstream outcome.

Treat a quantitative **pass** as a false pass when one or more of these are true:

- reviewer signoff verdict is `fail` or `revise` and cites that dimension
- operator rejects the artifact set for that dimension
- the project needed material revisions after a pass for that dimension

Treat a quantitative **fail** as a false fail when one or more of these are true:

- reviewer signoff verdict is `pass` and explicitly accepts that dimension
- operator accepts the artifact set without revision
- revisions were made only for unrelated dimensions

Compute per threshold and per scope:

- sample count
- pass count and fail count
- false-pass count and rate
- false-fail count and rate
- median measured value
- 80th and 90th percentile measured values
- reviewer disagreement examples with project links

Use scoped buckets in this order:

1. default/global threshold
2. per-medium threshold, when enough medium samples exist
3. per-preset threshold, when enough preset samples exist

Do not let a sparse preset bucket override strong medium evidence unless the preset has at least 5 relevant samples.

## Step 3 — Propose retune

Default tolerance:

- false-pass rate tolerance: 10%
- false-fail rate tolerance: 20%
- minimum sample count for automatic proposal: 5
- preferred sample count for confident proposal: 10

Proposal rules:

- If false passes exceed tolerance, tighten the threshold.
- If false fails exceed tolerance and false passes are within tolerance, loosen the threshold.
- If both false passes and false fails exceed tolerance, propose a manual review instead of a numeric change.
- If sample count is insufficient, propose no change unless the operator explicitly requested exploratory analysis.
- Never delete a threshold.
- Never change precedence semantics.
- Never move a preset-specific behavior into defaults unless multiple presets and mediums show the same pattern.

Numeric threshold proposal method:

- For max-style thresholds, propose the smallest value that would have passed at least 80% of accepted outcomes while failing the known bad outcomes when possible.
- For boolean consistency thresholds, propose changing the boolean only when reviewer and operator outcomes consistently show the current boolean is over-constraining or under-constraining the medium.
- Round proposed numeric values to readable increments: Delta E to whole numbers, Kelvin to nearest 50, ratios to two decimals, degrees to whole numbers, centroid distance to two decimals.

Each proposed change must include:

- threshold key
- current value
- proposed value
- scope: defaults, per_medium_overrides, or per_preset_overrides
- sample count
- false-pass rate before and estimated after
- false-fail rate before and estimated after
- examples supporting the change
- risks of the change

## Step 4 — Write proposal

Write:

`vault/archive/visual-aesthetics/proposals/coherence-threshold-{date}-proposal.md`

Required proposal frontmatter:

```yaml
---
type: coherence-threshold-calibration-proposal
created_at: "{machine-local timestamp}"
cadence: scheduled|on_demand
medium_filter: ""
preset_filter: ""
current_registry_version: 1
recommended_registry_version: 2
sample_count: 0
sample_size_status: sufficient|insufficient
dry_run: true|false
operator_approval_required: true
---
```

Required body sections:

- `# Coherence Threshold Calibration Proposal`
- `## Corpus`
- `## Current Threshold Resolution`
- `## Outcome Agreement`
- `## Proposed Changes`
- `## No-Change Thresholds`
- `## Risks`
- `## Operator Approval Checklist`

In `## Current Threshold Resolution`, explicitly restate precedence:

`defaults -> per_medium_overrides -> per_preset_overrides`

In `## Proposed Changes`, include a patch-style YAML excerpt, not an applied edit.

If `dry_run` is true, mark every proposed change as `DRY RUN ONLY`.

## Step 5 — Operator approves; bump version; archive prior

Only after explicit operator approval:

1. Copy the current registry to `vault/archive/visual-aesthetics/threshold-registries/artifact-coherence-thresholds-v{old_version}.yml`.
2. Edit `vault/config/artifact-coherence-thresholds.yml`.
3. Increment `version`.
4. Update `last_calibrated_at` using the machine-local clock.
5. Update `calibration_sample_count`.
6. Append calibration history entries for every changed threshold.
7. Validate the registry:

```bash
python3 scripts/validate_schema.py \
  --artifact vault/config/artifact-coherence-thresholds.yml \
  --schema schemas/artifact-coherence-thresholds.schema.json \
  --artifact-type yaml
```

8. Run coherence threshold tests:

```bash
pytest tests/test_coherence_thresholds.py -v
```

9. Add a short changelog note in the proposal file linking the archived prior registry.

Approval checklist:

- proposed values preserve deterministic override precedence
- default changes are justified by cross-medium data
- medium changes are justified by medium-specific data
- preset changes are justified by preset-specific data
- false-pass risk is lower or explicitly accepted by the operator
- schema validation passes
- threshold tests pass
