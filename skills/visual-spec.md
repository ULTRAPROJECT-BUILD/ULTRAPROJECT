---
type: skill
name: visual-spec
description: Locks the medium-specific visual contract. Universal layer (axes, references, mockups, multi-round adjudication, adversarial pass, gate, telemetry) plus medium plugin (mockup format, token families, parity methodology, presets). Build tickets cannot spawn until gate passes. Runs autonomously.
inputs:
  - project (required)
  - client (optional)
  - phase_number (optional)
  - wave_name (optional)
  - parent_brief_path (required)
  - visual_quality_target_medium (auto-detected from brief if not provided)
  - visual_quality_target_mode (auto-detected; default preset for sparse-coverage mediums = custom)
  - visual_quality_target_preset (auto-detected from brief signals; default = highest-confidence match for medium)
  - visual_axes (auto-derived from preset + brief; can be overridden if operator's initial prompt provides axis values)
  - operator_provided_references (optional)
  - operator_provided_brand (optional)
---

# Visual Specification Skill

## Mission

Run the Visual Specification phase from the parent brief to a locked,
gate-passing visual contract. This skill is executed by a `task_type:
visual_spec` ticket before UI build, self-review, quality-check, or
artifact-polish-review tickets may proceed.

The default operating mode is autonomous. Do not ask the operator to confirm
medium classification, preset selection, axis values, reference choices,
adjudication outcomes, adversarial conclusions, waiver handling, or gate
remediation. Operator checkpoints exist only when the initial prompt explicitly
included a directive parsed by `scripts/parse_initial_prompt_directives.py`.

The locked VS is not a mood board. It is a build contract:

- It pins the medium and aesthetic axes.
- It captures references and anti-patterns with hashes.
- It produces at least two locked anchor mockups.
- It runs multi-round visual adjudication with fresh reviewer sessions.
- It runs an adversarial adjacent-preset pass.
- It extracts tokens through the medium plugin.
- It validates contrast, specificity, provenance, parity, and gate state.
- It records telemetry fields needed by downstream visual-system learning.

Build tickets remain blocked until `tokens_locked: true` and
`check_visual_spec_gate.py --profile vs_full` passes.

`craft_depth` is part of the locked contract:

- `standard`: tokens plus static mockups. This is the default for `web_ui`
  dashboards and operational tools; no `artifact_manifest` is required.
- `enhanced`: adds an `artifact_manifest` for photographs, illustrations,
  and when useful 3D or motion choreography. This is the default for marketing,
  `brand_identity`, and video-led work.
- `obsessive`: adds cinematic video, sound, live prototypes, and
  microinteractions. Use this for production launches, agency-grade requests,
  and briefs that explicitly ask for the experience to feel alive.

Auto-promote from `standard` to `enhanced` when the brief asks for
Apple-grade hero animation, custom 3D, or a surface that feels alive. Promote
to `obsessive` for production launch or agency-grade language. Initial-prompt
operator directives still win when they explicitly set `craft_depth`.

If the source brief's `deliverable_type` is `product_app`, set `adjudication_rounds_required: 1` and `adversarial_pass_required: false`. Multi-round adjudication and adversarial pass are for brand-marketing-site deliverables. Product/app deliverables get a single-pass review.

## Inputs and Working Paths

Resolve these paths before starting:

- `project`: project slug.
- `client`: optional client slug.
- `parent_brief_path`: required governing creative brief or phase brief.
- `snapshots_path`: client-scoped snapshots path when `client` is present,
  otherwise the platform snapshots path.
- `visual_spec_root`: `{snapshots_path}/visual-spec/{project}` unless the
  ticket specifies a narrower phase or wave folder.
- `references_dir`: `{visual_spec_root}/references`.
- `mockups_dir`: `{visual_spec_root}/mockups`.
- `reports_dir`: `{visual_spec_root}/reports`.
- `tokens_dir`: `{visual_spec_root}/tokens`.
- `manifest_path`: `{visual_spec_root}/manifest.json`.
- `iteration_log_path`: `{references_dir}/iteration-log.md`.

Use the machine-local clock for artifact timestamps:

```bash
date +"%Y-%m-%dT%H:%M"
date +%Y-%m-%d
```

Do not infer local timestamps. Do not write naive UTC values where the platform
expects local time.

## Artifact Contract

The final VS snapshot must validate against
`schemas/visual-spec-frontmatter.schema.json`. The schema currently allows
medium path/version and medium-derived parity fields in frontmatter; the full
medium plugin snapshot goes in the body section `## Medium Plugin Snapshot`.

Required frontmatter fields include:

- `type: snapshot`
- `title`
- `project`
- `spec_scope`
- `parent_brief`
- `governs_tickets`
- `visual_quality_target_medium`
- `medium_plugin_version`
- `medium_plugin_path`
- `visual_quality_target_preset`
- `visual_quality_target_mode`
- `craft_depth`
- `visual_axes`
- `visual_axes_medium_extensions`
- `adjacent_preset_rejected`
- `adjacent_preset_rejection_reason`
- `references`
- `mockups`
- `adjudications`
- `adversarial_pass`
- `tokens_locked`
- `tokens_locked_at`
- `parity_targets`
- `contrast_validation`
- `outcome_data`
- `visual_specificity_contract`
- `visual_spec_id`
- `revision_id`
- `supersedes`
- `superseded_by`
- `active`
- `deprecated`
- `captured`
- `agent`
- `tags`

Use repository-relative paths in frontmatter. Absolute paths may be used in
commands, but the locked artifact should remain portable inside the vault.

## Step 1 - Resolve Medium Plugin (Autonomous)

Auto-classify the visual medium. Start with the parent brief:

```bash
python3 scripts/detect_visual_ambition.py \
  --brief "{parent_brief_path}" \
  --json-out "{references_dir}/visual-ambition.json"
```

`detect_visual_ambition.py` reports ambition signals. It does not fully resolve
medium, so combine it with brief keyword analysis and explicit
`visual_quality_target_medium` values when present.

Default medium disambiguation rules:

- Browser-rendered app, dashboard, console, marketing page, website, web tool,
  public page, admin panel, or React/Vite/Next surface -> `web_ui`.
- macOS, iOS, Android, Electron/Tauri native chrome, system settings, menu bar,
  mobile app, or desktop app -> `native_ui`.
- Deck, slide, keynote, sales deck, board deck -> `presentation`.
- Logo, identity, brand guide, visual identity, mark, type system -> `brand_identity`.
- Motion piece, launch video, reel, explainer, animation -> `video_animation`.
- 3D render, product render, scene, Blender, GLB, Three.js visual -> `3d_render`.
- PDF/report typography, white paper, publication, long-form document -> `document_typography`.
- Game HUD, game menu, game UI, inventory, health bar -> `game_ui`.
- Standalone charting, self-serve analytics, visualization system -> `data_visualization`.

If multiple media are plausible, choose the medium that governs the first build
ticket blocked by this VS. Do not prompt the operator. Record the losing
candidate and reason in `## Medium Resolution Notes`.

Load the medium plugin:

```bash
vault/archive/visual-aesthetics/mediums/{medium}.md
```

If the plugin is missing:

- For a sparse or unsupported medium, use `custom` mode with the project's
  references only if the medium can still be represented by the current
  `visual-spec-frontmatter` schema.
- Otherwise create a blocked remediation note that [[source-capability]] or
  [[build-mcp-server]] must supply the medium plugin before this VS can lock.

Copy the plugin's frontmatter fields into working state:

- `version`
- `mockup_format`
- `mockup_anchor_count_min`
- `mockup_revisions_per_anchor_min`
- `token_families`
- `token_extractor_script`
- `parity_methodology`
- `runtime_check_methodology`
- `gospel_template_path`
- `applicable_presets`
- `regression_replay_contract`

Embed the plugin contract in the VS artifact:

- Frontmatter: schema-allowed `medium_plugin_version`,
  `medium_plugin_path`, `visual_axes_medium_extensions`, and parity targets.
- Body: full `## Medium Plugin Snapshot` with copied plugin frontmatter and
  a short note naming the plugin body sections followed during mockup work.

## Step 2 - Resolve Aesthetic Profile (Autonomous)

Resolve `visual_quality_target_mode`, `visual_quality_target_preset`, and all
six universal axes without operator confirmation.

Use this selection order:

1. Explicit operator directive parsed from the initial prompt and passed by the
   orchestrator wins when it names a supported medium/preset/axis.
2. Existing brand-system evidence in project context wins over generic preset
   matching. If project files, brief, or operator-supplied brand assets include
   a named brand system, route to `brand_system` mode.
3. Explicit brief terms such as `Linear-style`, `Stripe Dashboard`, `Apple.com`,
   `macOS Settings`, or named `visual_quality_target_preset` select the matching
   preset when the medium plugin lists it.
4. If no explicit match exists, choose the highest-confidence preset from the
   medium's applicable list using brief signals:
   - operator queue, inbox, triage, issue review, approval, task workbench,
     keyboard-heavy, dense operations -> `operator_triage`
   - billing, customers, payments, subscriptions, risk, enterprise admin,
     ledger, financial operations -> `operator_admin`
   - product marketing, consumer launch page, cinematic product story,
     Apple-style product page -> `apple_consumer`
   - native macOS/iOS settings or preferences -> `apple_native`
5. If the medium has sparse preset coverage and no match is credible, route to
   `custom` mode using project references and explain why no preset applied.
6. Use `none` only when the initial prompt explicitly waives visual spec, or
   the gate policy permits no VS for this project. When ambition is detected,
   `none` requires a waiver artifact and should be rare.

Axis derivation:

- Start with preset frontmatter axes.
- Apply brief-specific overrides only when the brief gives concrete
  contradictory evidence, not vague taste words.
- Use canonical schema values:
  - `list_detail`, not list-detail.
  - `single_panel`, not single-pane.
  - `subtle`, not calm.
  - `functional`, not standard.
  - `web_native`, not web-app.
  - `approachable`, not consumer.
- Record human aliases in the body when useful for reviewer readability.

Adjacent preset:

- Read `adjacent_presets` from the selected preset file.
- Select the strongest nearby alternative as `adjacent_preset_rejected`.
- Write a substantive `adjacent_preset_rejection_reason` with at least two
  sentences. It must name concrete benefits the adjacent preset would offer and
  why those benefits are less important for this project.
- If no adjacent preset exists, choose the nearest preset from the same medium
  by axis similarity and mark the choice as inferred.

## Step 3 - Capture Reference Pack

Create `references_dir` and capture at least three primary references plus at
least one anti-pattern. More is better when the aesthetic is ambiguous.

Reference sources:

- Operator-provided references first.
- Brand-system assets second.
- Selected preset default reference pack third.
- Brief genre benchmarks fourth.
- Project-specific competitor or adjacent-product references fifth.

Capture each URL with `agent-browser` at the medium's standard viewport. For
web UI, use 1440 by 900 unless the plugin says otherwise:

```bash
agent-browser open "{url}"
agent-browser wait --load networkidle
agent-browser screenshot "{references_dir}/{slug}.png" --full
agent-browser close
```

If a URL blocks capture, replace it autonomously with the next best reference
from the preset pack or brief. Do not stop for operator confirmation.

For every PNG, compute hashes:

```bash
python3 scripts/compute_phash.py \
  --input "{references_dir}/{slug}.png" \
  --json-out "{references_dir}/{slug}.phash.json"

python3 scripts/compute_clip_centroid.py \
  --preset-name "{visual_quality_target_preset}" \
  --references "{references_dir}/{primary_1}.png" "{references_dir}/{primary_2}.png" "{references_dir}/{primary_3}.png" \
  --out "{references_dir}/clip-centroid.npy" \
  --json-out "{references_dir}/clip-centroid.json"
```

Record each reference in VS frontmatter with:

- `file`
- `sha256`
- `phash`
- `clip_embedding_hash`
- `width`
- `height`
- `source_url`
- `captured_at`
- `role`
- `note`

The anti-pattern is not a low-quality insult. It is a visual drift boundary.
Write its note as "Avoid this because..." with concrete risk language.

## Step 4 - Scaffold (Stage A)

Follow the selected medium plugin's Stage A instructions. For `web_ui`, create
self-contained HTML/CSS mockups in `mockups_dir` with no framework, no remote
fonts, no copied production source, no generic placeholder data, and no
decorative filler.

Create at least the plugin's `mockup_anchor_count_min` anchors. For web UI the
minimum is two:

- Primary workflow anchor.
- Secondary, structurally different state or screen.

Each scaffold must test layout topology, pane ratios, hierarchy, density,
state vocabulary, and action placement. Use realistic data drawn from the
brief. Do not use lorem ipsum.

Capture each scaffold:

```bash
python3 scripts/regen_mockup.py \
  --html "{mockups_dir}/scaffold-1-{anchor}-rev1.html" \
  --out-png "{mockups_dir}/scaffold-1-{anchor}-rev1.png" \
  --viewport 1440x900
```

Append to `iteration-log.md`:

- Anchor name.
- Source HTML.
- PNG path.
- Declared axes.
- What this scaffold tests.
- Known weaknesses to improve.

## Step 5 - Iterate (Stage B)

Each anchor needs at least three captured revisions before it can lock. The
revision loop is autonomous:

1. Capture the current revision.
2. Compare it against the primary references and anti-pattern.
3. Identify at least three concrete visual deltas.
4. Edit the mockup.
5. Re-capture.
6. Append the diff to `iteration-log.md`.

Revision notes must be specific. Bad: "make it cleaner." Good: "row height is
40px and only shows 12 work items; reduce to 32px and move secondary metadata
inline so the dense triage claim is visible."

For web UI, keep all revisions as source HTML plus PNG:

- `mockups/iter-1-{anchor}-rev1.html`
- `mockups/iter-1-{anchor}-rev1.png`
- `mockups/iter-1-{anchor}-rev2.html`
- `mockups/iter-1-{anchor}-rev2.png`
- `mockups/iter-1-{anchor}-rev3.html`
- `mockups/iter-1-{anchor}-rev3.png`

When an anchor is ready, copy the winning revision to:

- `mockups/locked-{anchor}.html`
- `mockups/locked-{anchor}.png`

The locked HTML is token source of truth. The locked PNG is visual parity source
of truth.

## Step 6 - Adjudicate (Stage C)

Spawn a fresh reviewer for visual spec adjudication. Use the runtime so the
review is isolated from the authoring context:

```bash
python3 scripts/agent_runtime.py spawn-task \
  --task-type visual_spec_review \
  --ticket-path "{review_ticket_path}" \
  --project "{project}" --client "{client}" \
  --force-agent visual_reviewer \
  --prompt "**FIRST-LOOK INSTRUCTION (mandatory before any rubric-based work):** Before reading any spec, manifest, gate report, schema, or running any validation script, use the Read tool to open every rendered PNG / screenshot / mockup image referenced in this review, including every locked/revision PNG in {mockups_dir} and any reference PNG/mockup image in {references_dir}. Look at each image with your own multimodal vision. Write a SHORT, HONEST paragraph (3-6 sentences) titled \"First-look gut reaction\" describing exactly what you see and how you would react if you were a smart human seeing this for the first time: is it actually beautiful, is it visually thin, does the subject appear, does it have warmth/personality/surprise, does it look like the kind of work the brief promised? Be specific. Be unflattering when warranted. The rubric-based grading that follows MUST explicitly engage with this gut reaction — if your gut says \"this looks basic\" or \"the subject is missing\" or \"this could be any generic editorial site,\" the rubric grading must either explain why the work succeeds despite that, or downgrade accordingly. The gut reaction CANNOT be silently ignored. If you cannot open the PNGs (paths missing, file unreadable), fail the review immediately — no rubric grade is valid without first-look. **OPERATOR-INTENT CONTEXT (load this BEFORE forming any judgment about alignment, register, or whether the work matches what was promised):** Resolve and read the project file for {project} — specifically the Context section (which contains the operator's original prompt verbatim or a link to the request snapshot) and the ## Taste / Visual Acceptance Criteria section (which contains active TC-NNN entries that are load-bearing project constraints). Resolve and read the project plan for {project}. You are not just grading the work against the spec — you are grading whether the work fulfills what the operator ACTUALLY ASKED FOR. The spec is downstream of the prompt; if the spec drifted from the prompt, the work matching the spec is not sufficient. State explicitly: (a) what the operator literally asked for in their prompt, (b) what the spec promised, (c) whether the work matches both — and if there is a gap between (a) and (b), flag it as a brief-spec drift even if the work matches (b). Run visual_spec_review for {project}. Read {iteration_log_path}, locked/revision PNGs in {mockups_dir}, reference pack in {references_dir}, and the medium plugin. Answer the four VS adjudication questions plus medium-specific extensions. Round 1 is a real review. If the work is genuinely peak, Round 1 may PASS; call REVISE when something actually needs revising and link findings to specificity fields."
```

The reviewer must answer four universal questions:

1. Does the selected aesthetic fit the brief better than the rejected adjacent
   preset?
2. Do the locked mockups visibly encode the six axes and medium extension
   values?
3. Do the references explain the choices without being copied literally?
4. Do the mockups contain project-specific domain, workflow, data, and affordance
   texture rather than generic UI?

Also require medium-specific questions from the plugin. For `web_ui`, include:

- Does the HTML/CSS implement the selected topology without equal-weight card
  grids unless that topology was selected?
- Are token families visible in the DOM/CSS rather than only named in prose?
- Do focus, hover, disabled, selected, and destructive states exist where the
  product needs them?
- Do the screenshots fit a 1440 by 900 work viewport without incoherent
  overlap or hidden primary actions?

Round 1 is a real review. If the work is genuinely peak, Round 1 may PASS. Mandatory disagreement reinforces in-register refinement and suppresses divergent feedback; we trust the reviewer to call REVISE when something actually needs revising.

On `REVISE`:

- Address redlines in the source mockups.
- Capture a new revision.
- Append a redline response to `iteration-log.md`.
- Spawn a different fresh `visual_reviewer` session for the next round.
- Record the new session id in frontmatter.

On `PASS`:

- Record the sign-off report.
- Ensure the final adjudication round is `PASS`.
- Continue to Stage D.

Sessions must be unique across adjudication rounds. The gate checks this.

## Step 7 - Adversarial Pass (Stage D)

Spawn another fresh `visual_reviewer`.

Prepend this to the adversarial reviewer prompt:

**FIRST-LOOK INSTRUCTION (mandatory before any rubric-based work):** Before reading any spec, manifest, gate report, schema, or running any validation script, use the Read tool to open every rendered PNG / screenshot / mockup image referenced in this review, including every locked/revision PNG in `{mockups_dir}` and any reference PNG/mockup image in `{references_dir}`. Look at each image with your own multimodal vision. Write a SHORT, HONEST paragraph (3-6 sentences) titled "First-look gut reaction" describing exactly what you see and how you would react if you were a smart human seeing this for the first time: is it actually beautiful, is it visually thin, does the subject appear, does it have warmth/personality/surprise, does it look like the kind of work the brief promised? Be specific. Be unflattering when warranted. The rubric-based grading that follows MUST explicitly engage with this gut reaction — if your gut says "this looks basic" or "the subject is missing" or "this could be any generic editorial site," the rubric grading must either explain why the work succeeds despite that, or downgrade accordingly. The gut reaction CANNOT be silently ignored. If you cannot open the PNGs (paths missing, file unreadable), fail the review immediately — no rubric grade is valid without first-look.

**OPERATOR-INTENT CONTEXT (load this BEFORE forming any judgment about alignment, register, or whether the work matches what was promised):** Resolve and read the project file for {project} — specifically the Context section (which contains the operator's original prompt verbatim or a link to the request snapshot) and the ## Taste / Visual Acceptance Criteria section (which contains active TC-NNN entries that are load-bearing project constraints). Resolve and read the project plan for {project}. You are not just grading the work against the spec — you are grading whether the work fulfills what the operator ACTUALLY ASKED FOR. The spec is downstream of the prompt; if the spec drifted from the prompt, the work matching the spec is not sufficient. State explicitly: (a) what the operator literally asked for in their prompt, (b) what the spec promised, (c) whether the work matches both — and if there is a gap between (a) and (b), flag it as a brief-spec drift even if the work matches (b).

The adversarial reviewer must pick the stronger of two challenges and commit:
(a) "A different register entirely would be better" — argue for an adjacent preset that is NOT on the brief's anti-pattern list. Banned-by-the-brief adversaries are tautological and do not count.
(b) "A higher-craft execution of the same register would be better" — name 2-3 real-world peer sites in the same register and enumerate the concrete craft moves they make that the locked mockup does not.

Pick whichever line of attack is stronger given the evidence. Verdict vocabulary: `selected_upheld | adjacent_preferred | peer_execution_preferred | revise`.

The adversarial report must include:

- `reviewer_session_id`
- `challenge_selected`: `different_register` or `same_register_higher_craft`
- For `different_register`, `adjacent_preset_argued` and at least one section arguing that adjacent preset's strongest case.
- For `same_register_higher_craft`, 2-3 real-world peer sites and the concrete craft moves they make that the locked mockup does not.
- Counted concrete missing benefits or missing craft moves.
- Evidence strength for each claim: strong, medium, weak.
- Verdict recommendation: `selected_upheld`, `adjacent_preferred`, `peer_execution_preferred`, or `revise`.

Autonomous defend-or-restart rule:

- Count concrete missing benefits supported by specific visual evidence.
- Count sentences in `adjacent_preset_rejection_reason`.
- If the reviewer cites three or more concrete missing benefits and the author
  rejection reason has fewer than two sentences, restart from Stage A using the
  adjacent preset or an explicitly blended custom profile.
- Otherwise defend the selected preset and proceed.

Record the decision in the VS artifact:

- `adversarial_pass.verdict: selected_upheld` when defended.
- `adversarial_pass.verdict: revise` when more revision is needed.
- `adversarial_pass.verdict: peer_execution_preferred` when higher-craft same-register execution is preferred.
- `adversarial_pass.verdict: adjacent_preferred` only when restarting.

Do not ask the operator. The operator can review only if the initial directives
requested `OPERATOR_REVIEW VS_ADJUDICATION`.

## Step 8 - Token Extraction (Stage E)

Run the medium plugin's extractor against locked mockups. For `web_ui`:

```bash
python3 scripts/extract_tokens_from_web_ui.py \
  --mockup "{mockups_dir}/locked-{anchor}.html" \
  --out "{tokens_dir}/{anchor}-tokens.json"
```

Merge anchor token files into `manifest.json` with these top-level keys:

- `project`
- `medium`
- `tokens`
- `assets`
- `mockups`
- `references`
- `visual_axes`
- `visual_quality_target_mode`
- `visual_quality_target_preset`
- `adjacent_preset_rejected`

All plugin-declared token families must be present. For `web_ui`, that means:

- `color`
- `type`
- `spacing`
- `radius`
- `elevation`
- `motion`
- `density`
- `focus`

Run schema validation for the token payload when a medium token schema exists:

```bash
python3 scripts/validate_schema.py \
  --artifact "{tokens_dir}/web-ui-token-payload.json" \
  --schema schemas/token-payload-web_ui.schema.json \
  --artifact-type json
```

If token extraction misses required families, fix the locked mockup CSS so the
tokens actually exist and re-run extraction. Do not paper over missing tokens
with manifest-only placeholders.

## Step 9 - Contrast Validation

Run contrast validation after token extraction:

```bash
python3 scripts/check_contrast.py \
  --manifest "{manifest_path}" \
  --json-out "{reports_dir}/contrast.json"
```

If contrast fails:

- For ordinary color choices, adjust colors in locked mockups, re-render,
  re-extract tokens, and re-run contrast.
- For unavoidable failures caused by operator-provided brand constraints,
  regulatory screenshots, or fixed media, create a waiver entry with the
  required waiver fields in `vault/config/visual-spec-waivers.md`.
- If initial directives include `APPROVE WAIVER MANUALLY`, pause at the waiver
  point and use the existing operator-attention mechanism.
- Without that directive, handle waivers autonomously when policy permits them.

The final VS frontmatter `contrast_validation` must summarize the result:

- `wcag_level`
- `min_ratio_normal`
- `min_ratio_large`
- `violations`

## Step 10 - Lock and Gate

Assemble the final VS snapshot at:

```text
{snapshots_path}/{date}-visual-spec-{project}.md
```

Set:

- `tokens_locked: true`
- `tokens_locked_at: {local timestamp with timezone}`
- `active: true`
- `deprecated: false`
- `visual_spec_id`: stable UUID for the logical spec.
- `revision_id`: new UUID for this revision.
- `resolver_generation`: record in dependent tickets from resolver output.

Run the full gate:

```bash
python3 scripts/check_visual_spec_gate.py \
  --vs-path "{visual_spec_path}" \
  --references-dir "{references_dir}" \
  --ticket-path "{ticket_path}" \
  --signoff-paths "{reports_dir}/adjudication-round-1.md" "{reports_dir}/adjudication-round-2.md" "{reports_dir}/adversarial-pass.md" \
  --medium "{visual_quality_target_medium}" \
  --profile vs_full \
  --brief "{parent_brief_path}" \
  --json-out "{reports_dir}/visual-spec-gate.json" \
  --markdown-out "{reports_dir}/visual-spec-gate.md"
```

Default `vs_full` uses warn-on-skip for cold-start production installs. Pass
`--strict` only when `vault/config/brief-contract-collusion-baseline.json`
exists from at least five historical projects and
`vault/config/visual-spec-waivers.md` has entries from at least one project that
triggered ambition detection. Warm-state production runs should use `--strict`;
cold-start runs accept skipped cold-start checks as warnings.

On `PASS`, the VS is locked. Build tickets can spawn.

On `FAIL`, remediate autonomously. Common remediations:

- Missing references: capture replacement references and recompute hashes.
- Missing anti-pattern: add a drift boundary and update frontmatter.
- Too few revisions: create another revision and append `iteration-log.md`.
- No final PASS adjudication: spawn another fresh reviewer after revision.
- Session reuse: discard invalid reviewer report and spawn a new session.
- Token family missing: adjust locked CSS and re-extract.
- Semantic layout fail: revise topology, pane dominance, hierarchy, or density.
- Specificity fail: add project-specific domain entities, workflow signatures,
  data texture, and affordances to mockups, not just prose.
- Contrast fail: adjust colors or write a policy-valid waiver.

Retry the gate after each remediation. Maximum autonomous remediation attempts:
three. On the fourth consecutive failure, escalate to the operator using the
existing operator-attention mechanism and include the last three gate reports.

## Step 11 - Artifact Manifest Production

Run this step when `craft_depth` is `enhanced` or `obsessive`. It is part of
the default autonomous VS flow and does not create an operator confirmation
point unless a producer is missing, remediation is exhausted, or an initial
directive explicitly requested an operator checkpoint.

Analyze the locked mockups and parent brief, then declare every required
non-token artifact in the VS frontmatter `artifact_manifest` block. The block
must match `schemas/artifact-manifest.schema.json`. For each item include the
artifact type, prompt or prompt template, target slot, slot contract when the
artifact must fit into a medium-owned slot, and the intended dimensions or
count. Enhanced work normally includes photographs, illustrations, product 3D,
scene 3D, or motion choreography. Obsessive work may also include cinematic
video, sound, live prototype artifacts, and microinteraction assets.

For each manifest item, resolve the producer before invocation:

```bash
python3 scripts/artifact_registry.py resolve \
  --artifact-type "{artifact_type}" \
  --medium "{visual_quality_target_medium}"
```

If no active producer resolves, pause the project by writing
`{date}-missing-producer-{type}.md` under the project snapshots folder. The
report must match `schemas/missing-producer-report.schema.json` and state the
artifact type, project context, slot constraints, candidate producers, and the
available operator decisions: register a producer through
`register-artifact-producer`, skip or degrade the manifest item, adjust the
slot contract, or choose an alternative artifact. Resume only after the
producer exists or the manifest is deliberately changed.

When a producer resolves, invoke it with the artifact prompt plus any
`slot_contract` constraints. Run the producer-owned quality gate first. Then,
when `slot_contract` is present, run the medium-owned slot integration check:

```bash
python3 scripts/check_slot_integration.py \
  --artifact-path "{locked_candidate_path}" \
  --artifact-type "{artifact_type}" \
  --slot-contract-json "{slot_contract_json}" \
  --medium "{visual_quality_target_medium}"
```

On slot integration failure, run the remediation flow rather than asking the
operator immediately:

```bash
python3 scripts/run_slot_remediation.py \
  --artifact-id "{artifact_id}" \
  --slot-contract-json "{slot_contract_json}" \
  --producer-id "{producer_id}" \
  --original-prompt "{prompt}" \
  --quality-gate-pass-required true \
  --project "{project}"
```

The remediation order is re-prompt with slot constraints, then fallback
producer, then a slot-incompatibility report with an operator decision. A
successful re-prompt or fallback must update the manifest item with the locked
artifact path, hash, quality gate result, slot integration result, production
attempts, and any `producer_substitution_for_slot`.

After all artifacts are produced and locked, write an artifact set JSON and run
the cross-artifact coherence check:

```bash
python3 scripts/check_artifact_coherence.py \
  --artifact-set-json "{reports_dir}/artifact-set.json" \
  --vs-path "{visual_spec_path}" \
  --thresholds-yaml "vault/config/artifact-coherence-thresholds.yml" \
  --reviewer-mode auto \
  --json-out "{reports_dir}/artifact-coherence.json"
```

Spawn a fresh reviewer round to fill the VS frontmatter `coherence_signoff`
block matching `schemas/coherence-signoff.schema.json`. The reviewer must cite
each quantitative set check: palette delta, color temperature variance, type
discipline, lighting vocabulary, motion tempo, audio mood, spatial scale, and
per-slot integration. If coherence fails, re-produce mismatched artifacts with
adjusted prompts and rerun coherence. Limit this loop to three cycles before
escalating with the artifact set, coherence reports, and the exact mismatches.

When `visual_quality_target_mode` is `custom`, assign and persist the custom
cohort before final gate rerun:

```bash
python3 scripts/cluster_custom_aesthetics.py \
  --vs-path "{visual_spec_path}" \
  --json-out "{reports_dir}/custom-cohort.json"
```

Pin every locked artifact in VS frontmatter with repository-relative paths and
SHA-256 hashes. Also record centroid versions used by artifact quality gates
and coherence thresholds used by `check_artifact_coherence.py`, so checks 89-97
can verify the artifact set at lock time and runtime.

## Operator Override Directives

Operator override is parsed only from the initial prompt by:

```bash
python3 scripts/parse_initial_prompt_directives.py \
  --prompt-text "{operator_initial_prompt}" \
  --json-out "{snapshots_path}/{date}-directives-{project}.json"
```

This skill consumes the directives JSON path passed by the orchestrator.

Supported checkpoints:

- `STOP AFTER VS_LOCK`: pause after Step 10 success, record state, and await
  operator unblock before build tickets spawn.
- `OPERATOR_REVIEW VS_ADJUDICATION`: pause after Stage C adjudication records
  are complete. The visual-spec executor still performs default autonomous
  revisions before the pause.
- `APPROVE WAIVER MANUALLY`: flips otherwise autonomous waiver handling into an
  operator-attention checkpoint.

Unsupported or ambiguous operator messages inside later project artifacts do
not create checkpoints. Only the parsed initial-prompt directives do.

## Outputs

Write these artifacts:

- `{references_dir}/visual-ambition.json`
- `{references_dir}/reference-*.png`
- `{references_dir}/reference-*.phash.json`
- `{references_dir}/anti-pattern-*.png`
- `{references_dir}/clip-centroid.npy`
- `{references_dir}/clip-centroid.json`
- `{references_dir}/iteration-log.md`
- `{mockups_dir}/scaffold-*`
- `{mockups_dir}/iter-*`
- `{mockups_dir}/locked-{anchor}.html`
- `{mockups_dir}/locked-{anchor}.png`
- `{reports_dir}/adjudication-round-{N}.md`
- `{reports_dir}/adversarial-pass.md`
- `{reports_dir}/contrast.json`
- `{tokens_dir}/{anchor}-tokens.json`
- `{tokens_dir}/{medium}-token-payload.json`
- `{visual_spec_root}/manifest.json`
- `{reports_dir}/visual-spec-gate.json`
- `{reports_dir}/visual-spec-gate.md`
- `{reports_dir}/artifact-set.json` when `craft_depth` is enhanced or obsessive
- `{reports_dir}/artifact-coherence.json` when `artifact_manifest` is present
- `{reports_dir}/custom-cohort.json` when `visual_quality_target_mode` is custom
- `{snapshots_path}/{date}-visual-spec-{project}.md`

Dependent UI build/review tickets must receive these metadata fields after the
orchestrator resolves the locked VS:

- `visual_spec_path`
- `visual_spec_anchor_mockups`
- `visual_spec_references_dir`
- `visual_spec_locked_at`
- `visual_axes`
- `visual_quality_target_preset`
- `visual_quality_target_medium`
- `visual_quality_target_mode`
- `visual_spec_id`
- `revision_id`
- `resolver_generation`

## Failure Modes

- **Ambiguous medium:** choose the medium governing the imminent build ticket,
  record alternatives, continue.
- **No preset match:** use `custom` mode with project references for sparse
  coverage mediums; for supported web/native surfaces choose the closest
  medium-listed preset.
- **Reference capture blocked:** replace the URL with another real reference
  from the preset, brand, or brief. Record the replacement.
- **CLIP dependency missing:** write the dependency error, keep pHash and SHA
  records, and run the gate. If the gate requires CLIP, remediate by installing
  the expected dependencies through the normal capability path or escalate only
  after three failed autonomous attempts.
- **Reviewer gives an unsupported Round 1 verdict:** discard the report and
  spawn a fresh reviewer with the real-review instruction.
- **Reviewer session reused:** discard the duplicated report and spawn a fresh
  reviewer.
- **Adversarial pass prefers adjacent preset:** apply the autonomous
  defend-or-restart rule. Restart from Stage A only when the rule says so.
- **Contrast waiver needed:** write a policy-valid waiver autonomously unless
  `APPROVE WAIVER MANUALLY` is present.
- **Gate remains red after three remediation attempts:** escalate with the gate
  reports, iteration log, and a precise list of unresolved checks.

## See Also

- [[orchestrator]]
- [[creative-brief]]
- [[project-plan]]
- [[quality-check]]
- [[self-review]]
- [[artifact-polish-review]]
- [[deliverable-standards]]
