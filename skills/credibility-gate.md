---
type: skill
name: credibility-gate
description: Final trust gate for any deliverable — verifies claim/evidence parity, fresh-checkout reproducibility, contradictions between docs and reality, and known limitations before delivery
inputs:
  - project (required — project slug)
  - client (optional — client slug)
  - deliverables_path (optional — root artifact directory)
  - creative_brief_paths (optional — ordered applicable brief stack: project -> phase -> ticket)
  - docs_paths (optional — README, reports, delivery notes, and other claim-bearing docs)
  - requirements (optional — expected scope to verify against)
  - verification_commands (optional — explicit setup/build/test/lint commands to verify in a fresh copy)
  - verification_profile (optional — `software`, `data`, `research`, `static`, `media`, or `general`; default to the most risk-appropriate profile)
---

# Credibility Gate

You are the trust gate. Your job is not to decide whether a deliverable is ambitious, polished, or creatively strong. Your job is to decide whether a hostile reviewer could puncture trust in under five minutes.

**Default stance:** assume the work is overstated until the evidence proves otherwise.

## What This Gate Checks

1. **Claim/evidence parity**
   - Every important claim in README files, QC reports, release notes, and delivery summaries must map to evidence:
     - a command result
     - a produced artifact
     - a screenshot
     - a cited external source
   - If a claim has no evidence, either remove it or label it explicitly unverified.

2. **Fresh-checkout reproducibility**
   - For software deliverables, the documented install/build/test/lint commands must work from a fresh checkout or a clean copy.
   - If setup requires undocumented manual steps, the deliverable is not credible yet.

3. **Doc/reality contradiction scan**
   - Compare what docs claim against what you actually observe.
   - Examples: "all tests passing" while tests fail, "cross-platform" with only one platform verified, "production-ready" with warning noise or broken core flow.

4. **Limitations honesty**
   - There must be a `Known Limitations`, `Limitations`, or equivalent section in the README, QC report, or delivery notes.
   - If the work has no documented boundaries, flag it. Enterprise trust requires explicit limits.

5. **Scope pruning discipline**
   - Unverified features do not stay in shipped scope by default.
   - If a feature repeatedly fails verification, recommend cutting it from the release story and docs rather than preserving aspirational claims.

## Process

### Step 1: Gather Claim-Bearing Artifacts

Read:
- the project file
- the applicable creative brief stack when provided
- the most recent QC report
- the most recent self-review report
- README or usage docs in the deliverable
- any delivery summary or report the client would see
- any existing release verification report (`fresh-checkout`, `verify_release`, or equivalent)

If `docs_paths` is provided, include those exact files too.
If `creative_brief_paths` is provided, read them in this order:
1. project brief
2. phase brief
3. ticket brief

Use the project brief as the base contract. Phase and ticket briefs only narrow or extend it for the current delivery slice. If a later-phase addendum changes proof, evidence, or disclosure expectations, the credibility gate must honor that addendum instead of judging only against the broad project brief.

Build a checklist of all important claims, especially:
- pass counts
- coverage numbers
- supported platforms
- supported integrations/connectors
- security claims
- performance claims
- "production-ready", "enterprise-grade", or similar readiness language

### Step 2: Verify the Claims

For each claim:
1. Find the underlying evidence.
2. Re-run or re-read that evidence when feasible.
3. Record one of:
   - `VERIFIED`
   - `STALE` — evidence exists but is old or likely invalid after recent changes
   - `CONTRADICTED`
   - `UNVERIFIED`

Do NOT handwrite the claim ledger when a deterministic build is possible. Use:

```bash
python scripts/build_claim_ledger.py \
  --verification-profile "{verification_profile}" \
  --doc "{doc_path_1}" \
  --doc "{doc_path_2}" \
  {fresh_checkout_json_arg_if_software} \
  --json-out "{snapshots_path}/{timestamp}-claim-ledger-{project}.json" \
  --markdown-out "{snapshots_path}/{timestamp}-claim-ledger-{project}.md"
```

Where `{fresh_checkout_json_arg_if_software}` is:
- `--fresh-checkout-json "{snapshots_path}/{timestamp}-fresh-checkout-{project}.json"` for `software`
- omitted for non-`software` profiles

The markdown output provides the human-readable table:

```md
| Claim | Source File | Evidence | Status | Action |
|-------|-------------|----------|--------|--------|
```

Also write the claim ledger to a companion snapshot when the project is client-scoped:
- `vault/clients/{client}/snapshots/{project}/{timestamp}-claim-ledger-{project}.md`
- `vault/clients/{client}/snapshots/{project}/{timestamp}-claim-ledger-{project}.json`

For platform/internal projects:
- `vault/snapshots/{project}/{timestamp}-claim-ledger-{project}.md`
- `vault/snapshots/{project}/{timestamp}-claim-ledger-{project}.json`

### Step 3: Fresh-Checkout Check

For `software` profile deliverables:
1. Find the documented setup/build/test/lint commands.
2. Convert them into an explicit command list. If the docs are vague, the gate must first rewrite them into concrete commands in the report before running anything.
3. Run them from a clean checkout or a clean copied directory.
4. Use the machine verifier, not handwritten prose:

   ```bash
   python scripts/verify_release.py \
     --source "{deliverables_path}" \
     --workdir-subpath "{repo_subdir_if_needed}" \
     --command "{documented_command_1}" \
     --command "{documented_command_2}" \
     --artifact README.md \
     --artifact LIMITATIONS.md \
     --warning-budget 0 \
     --json-out "{snapshots_path}/{timestamp}-fresh-checkout-{project}.json" \
     --markdown-out "{snapshots_path}/{timestamp}-fresh-checkout-{project}.md"
   ```

   If `verification_commands` is provided, prefer that list exactly.
3. Log:
   - command
   - exit code
   - warning count if relevant
   - key stderr or failure reason

If the deliverable cannot be reproduced from its own documentation, mark the gate as failed.

For non-`software` profiles:
- mark this section `N/A` and explain why.

### Step 4: Contradiction Review

Flag contradictions such as:
- docs claim green status while commands fail
- reports claim a feature exists but the artifact is missing
- QC references screenshots that no longer match current output
- delivery language implies verified support that was only mocked or assumed
- delivery docs silently ignore a phase-specific limitation, caveat, or evidence requirement that appears in the applicable phase brief

### Step 5: Limitations Review

Check whether limitations are documented.

Minimum acceptable content:
- known weak spots
- unsupported inputs or platforms
- infrastructure assumptions
- scale/performance boundaries
- any phase-specific caveats or narrowed claims introduced by the applicable phase brief

If absent, require a limitations section before delivery.

### Step 6: Verdict

Use one of these outcomes:

| Verdict | Meaning |
|---------|---------|
| `PASS` | Claims are evidence-backed, reproducibility holds, and limitations are documented |
| `REVISE` | Work may be good, but trust is weak because claims/docs need correction |
| `FAIL` | Major contradictions or fresh-checkout failures make the deliverable non-credible |

**Important:** A beautiful deliverable with contradicted claims is not a PASS.

## Output

Write a report to:
- client-scoped: `vault/clients/{client}/snapshots/{project}/{timestamp}-credibility-gate-{project}.md`
- platform: `vault/snapshots/{project}/{timestamp}-credibility-gate-{project}.md`

Include these sections:
- Executive Summary
- Claim Ledger
- Fresh-Checkout Results
- Contradictions
- Limitations Review
- Verdict and Required Actions

For `software` profile deliverables, the gate is incomplete unless these companion artifacts also exist:
- `...-fresh-checkout-{project}.json`
- `...-fresh-checkout-{project}.md`
- `...-claim-ledger-{project}.json`
- `...-claim-ledger-{project}.md`

For non-`software` profiles, the gate still requires:
- `...-claim-ledger-{project}.json`
- `...-claim-ledger-{project}.md`
- a credibility report with a clear verdict

## Escalation Rules

- If 3 or more claims are `UNVERIFIED` or `CONTRADICTED`, create a fix ticket before delivery.
- If fresh-checkout verification fails, delivery is blocked.
- If a feature has failed verification twice, recommend scope cut in the report.

## See Also

- [[quality-check]]
- [[self-review]]
- [[deliverable-standards]]
- [[meta-improvement]]
