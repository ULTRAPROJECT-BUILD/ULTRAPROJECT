---
type: medium-plugin
medium: video_animation
version: "1.0"
description: "Motion sequence visual contracts for frame pacing, audio bed, type in motion, and timeline behavior."
applicable_aesthetic_axes:
  density: [sparse, balanced, dense]
  topology: [storyboard, timeline, narrative_sequence]
  expressiveness: [restrained, expressive, playful, cinematic]
  motion: [subtle, functional, expressive, cinematic, rapid]
  platform: [cinematic]
  trust: [approachable, professional, enterprise, luxury]
medium_extension_axes:
  pacing_register:
    description: "Temporal energy level that governs holds, cuts, sync, and visual event density."
    values: [calm, dramatic, rapid]
    required: true
mockup_format: frame_strip_pngs_plus_audio_waveform_plus_timeline_json
mockup_anchor_count_min: 3
mockup_revisions_per_anchor_min: 3
token_families: [frame_pacing, motion_curve, type_in_motion, audio_bed, color_grade, transition_vocab]
token_extractor_script: scripts/extract_tokens_from_video_animation.py
parity_methodology:
  method: frame_strip
  renderer_script: scripts/preset_regression_check.py
  comparison_metrics: [frame_phash_delta, timeline_token_presence, audio_waveform_presence, transition_vocab_match]
  thresholds:
    frame_motion_noise_floor: 8
    timeline_token_presence_min_pct: 85
    waveform_duration_min_s: 1
  required_artifacts: [png, json, waveform]
runtime_check_methodology:
  capture_method: frame_strip_and_audio_waveform_export
  checks: [frame_motion, timeline_order, audio_presence, type_legibility]
  budgets:
    render_seconds: 180
    token_walk_seconds: 45
gospel_template_path: skills/templates/gospel-video_animation.md
applicable_presets: [vercel_marketing, playful_consumer]
regression_replay_contract:
  supported: false
  renderer_script: scripts/preset_regression_check.py
  required_source_artifacts: [timeline_json, frame_strip, waveform]
  supported_token_mutations: []
  unsupported_token_mutations: ["*"]
  unsupported_mutation_behavior: operator_review
  replay_fixture: tests/fixtures/replay-video_animation/
  replay_determinism_test: operator_review_required
---
# video_animation Medium Plugin

## Overview

Video Animation visual specifications cover Lottie animations, Rive timelines, After Effects JSON exports, product videos, social ads, explainers, launch openers, motion graphics, and animated UI sequences.

This medium excludes static slide decks, game engine HUDs without timeline craft, and one-off static hero images.

The locked mockup format is `frame_strip_pngs_plus_audio_waveform_plus_timeline_json`. The minimum anchor set is 3 anchors: opener, middle, closer.

The plugin exists because this medium has failure modes that universal visual axes cannot catch alone.
The universal layer says what visual posture is intended. This medium layer says what artifact, token, replay, and runtime evidence proves that posture.

Every visual specification using this medium must name the universal six axes and the medium extension axis.
The extension values are: calm, dramatic, rapid.

The medium plugin is not a style guide. It is a build contract.
A build agent receives the locked mockups, extracted token payload, iteration log, reference pack, anti-patterns, and this plugin snapshot.
Any runtime implementation that cannot trace visible choices back to those artifacts fails the visual gate.

The default workflow is medium-aware:
- Stage A creates rough anchors in the native source format.
- Stage B iterates every anchor through at least three captured revisions.
- Stage E extracts tokens from source artifacts, not from prose.
- Parity checks compare regenerated or runtime evidence to locked anchors.
- Runtime checks verify that delivered artifacts preserve the same visual contract.

For video_animation, token extraction covers: frame_pacing, motion_curve, type_in_motion, audio_bed, color_grade, transition_vocab.
These families are required because they describe the medium-specific decisions most likely to drift during implementation.
If a project needs an unlisted family, create a Visual Specification amendment before build work begins.

Human-facing documents may use spaces, hyphens, or platform naming when describing axes.
Frontmatter uses schema-safe identifiers so the mechanical gate can validate the plugin without interpretation.

The plugin must travel with each locked Visual Specification snapshot.
A later update to the archive plugin does not retroactively change a project that already locked this version.
If the project reopens visual work after a plugin update, the amendment must state whether it keeps the old plugin snapshot or migrates to the new one.

Medium classification is part of the contract.
When the brief spans multiple mediums, create one Visual Specification per primary deliverable or explicitly name the dominant medium and the supporting evidence.
A chart-heavy deck can use `presentation` with chart tokens inside slides, but a standalone chart library deliverable should use `data_visualization`.
A native app landing page inside a web shell should use `web_ui`; a simulator or platform app should use `native_ui`.

The plugin's thresholds are minimums.
Project-specific quality bars may tighten them when a regulated, premium, clinical, financial, or public launch context demands it.

## Stage A operation (Scaffold)

Stage A creates rough anchors before polish. The purpose is to test structure, hierarchy, and source-format viability.

Create at least 3 anchor mockups. Required examples for this medium: opener, middle, closer.

Every Stage A anchor must include:
- A source artifact in the declared mockup format.
- A captured PNG or frame evidence artifact.
- A short note explaining which workflow, page, state, shot, or sequence the anchor represents.
- Declared universal axes and the medium extension-axis value.
- Enough realistic project content to prove the layout is not generic.

The scaffold may be visually rough. It may not be content-free.
The scaffold must expose the hard decision for the medium: hierarchy, density, pacing, mark usage, scene setup, page rhythm, HUD readability, or chart grammar.

Required Stage A naming:
- `mockups/scaffold-1-{anchor}-rev1` plus the source extension for frame_strip_pngs_plus_audio_waveform_plus_timeline_json.
- `mockups/scaffold-1-{anchor}-rev1.png` or the closest rendered evidence format.
- `visual-references/iteration-log.md` entry for every scaffold.

Do not use placeholder scaffolds that hide the actual visual problem.
Do not use generic sample data when the brief gives domain entities.
Do not borrow another medium's shortcut just because it is easier to render.

Stage A must answer these questions:
- Does the source format support the declared medium without lossy conversion?
- Are the anchor choices representative of the product's hardest visual states?
- Are the token families visible or extractable from the source artifact?
- Is the extension-axis value reflected by concrete visual decisions?
- Would a build agent know which runtime screen or deliverable maps to this anchor?

Stage A capture notes must include viewport, page size, frame index, camera name, device class, or chart dimensions as appropriate.
If a capture requires a simulator, renderer, deck export, or game engine, record the exact command or manual export path.
If a source tool is unavailable, record the fallback and mark the missing tool as a blocking risk before Stage B.

Before Stage A closes, the operator or author must reject anchors that are all the same composition.
The anchors should differ in the way users or viewers experience the medium.
For example, default and settings screens are different in native UI; title and dense chart slides are different in presentation; hero and alternate camera views are different in 3D.

Stage A is allowed to reveal that the selected medium is wrong.
If the deliverable is actually another medium, amend the Visual Specification instead of forcing mismatched artifacts through this plugin.

Stage A forbidden shortcuts:
- Do not create only one artboard and crop it into multiple anchors.
- Do not claim a source file exists when only a screenshot is present.
- Do not use unrelated template content just to satisfy anchor count.
- Do not defer all medium-specific details to implementation.
- Do not hide missing source structure behind a polished PNG.
- Do not use another project as the source without preserving provenance.
- Do not lock a default tool theme as if it were a project-specific visual direction.

Stage A evidence checklist:
- Source artifact opens locally or has a documented export route.
- Rendered artifact is nonblank.
- Anchor slug appears in the manifest draft.
- Axis values are visible in the artifact.
- Token families are visible, extractable, or explicitly marked manual.
- The reviewer can tell why this anchor matters.

## Stage B operation (Iterate)

Stage B turns rough anchors into locked visual evidence through deliberate revision.
Every anchor requires at least three captured revisions before it can be locked.

Each revision loop must:
1. Render or export the current source artifact.
2. Compare it against reference captures and anti-patterns.
3. Identify at least three concrete deltas.
4. Change the source artifact.
5. Re-render evidence.
6. Append a diff entry to `iteration-log.md`.

A revision delta must be inspectable.
Acceptable deltas name exact changes: type size, grid margin, light angle, frame hold, HUD safe-zone, chart scale, lockup clear-space, or page leading.
Unacceptable deltas say only that the artifact is cleaner, more premium, more modern, better, cinematic, or polished.

Required Stage B naming:
- `mockups/iter-1-{anchor}-rev1.*`
- `mockups/iter-1-{anchor}-rev2.*`
- `mockups/iter-1-{anchor}-rev3.*`
- `mockups/locked-{anchor}.*`

For source artifacts with multiple files, keep a stable anchor slug across source, PNG, JSON, timeline, deck, config, or page evidence.
The final locked artifact must have a manifest entry linking source path, rendered evidence path, capture method, and token payload.

Stage B must preserve:
- The declared medium.
- The declared extension-axis value.
- The representative workflow or state of the anchor.
- Token extractability.
- Reference provenance.
- Anti-pattern divergence.
- Specific project content.

Stage B should improve at least one of these medium-specific concerns on every revision:
- Composition hierarchy.
- Information density.
- Typography or label legibility.
- Color and state semantics.
- Motion or pacing discipline.
- Spatial grid or safe area.
- Source artifact determinism.
- Runtime feasibility.

The locked anchor must not depend on the reviewer's memory.
It must carry enough source evidence that another agent can regenerate, inspect, and implement it.

If a third revision is visually worse than the second, keep iterating.
The minimum revision count is a floor, not approval.
If a revision introduces generic defaults from a source tool, call that out in the log and remove them before locking.

Stage B closes only when a reviewer can answer the universal Visual Specification adjudication questions and the medium-specific questions below using evidence links.

The iteration log should use this shape for every revision:
- Anchor slug.
- Source artifact path.
- Rendered evidence path.
- Three concrete changes since the previous revision.
- Reference or anti-pattern that motivated the change.
- Remaining weakness.
- Reviewer status.

When revisions use binary source tools, export a lightweight sidecar JSON, XML, SVG, CSS, or text summary whenever possible.
The sidecar does not replace source, but it makes review and token extraction auditable.

## Stage E operation (Token extraction)

Stage E extracts tokens from the locked source artifacts.
Run the extractor with: `python3 scripts/extract_tokens_from_video_animation.py --mockup PATH --out visual-references/tokens-video_animation.json`.

Accepted source inputs include: Lottie JSON, Rive timeline JSON, After Effects bodymovin JSON, timeline JSON, frame-strip PNGs.
The extractor reads frame rate, in/out points, keyframe easing, text layers, audio metadata, color filters, and transition names from timeline JSON.

The extractor output must match the token-payload schema for this medium.
It must contain every token family listed in plugin frontmatter.
It should prefer named source tokens over inferred fallback values.

Token extraction rules:
- Read source artifacts, not screenshots, when structured source is available.
- Treat PNGs as evidence, not the primary token source.
- Preserve source token names when the source tool provides them.
- Normalize units into the schema's expected values.
- Warn when a family is inferred from fallback values.
- Fail when required manual families are incomplete.

The manifest must embed the token payload or link to it with a stable relative path.
The Visual Specification body should summarize only the important decisions. The JSON payload is authoritative for build enforcement.

If the extractor cannot parse the provided source format, do not hand-edit a fake payload.
Export a supported source format, add a parser, or create a Visual Specification amendment that records the unsupported path.

If the source tool requires a heavy dependency, the extractor must fail with exit code 2 and instructions instead of silently producing partial tokens.
This keeps build agents from implementing incomplete visual contracts.

The extraction report should record warnings.
Warnings are acceptable for inferred optional values.
Warnings are not acceptable for missing required token families.
If a required family is inferred, the Visual Specification should say why no better structured source was available.

## Parity methodology

Parity for video_animation uses `frame_strip` comparison.
Primary acceptance threshold: The frame strip must show meaningful pHash movement above the noise floor and the audio/timeline tokens must match the locked contract.

The parity packet must include:
- Required artifacts: png, json, waveform.
- Comparison metrics: frame_phash_delta, timeline_token_presence, audio_waveform_presence, transition_vocab_match.
- A manifest link from every locked anchor to its source and rendered evidence.
- A token payload generated after the final locked revision.
- A note explaining any unsupported deterministic replay path.

Parity is not an aesthetic vote.
Parity confirms that the locked visual contract can be regenerated or matched by runtime evidence.
A beautiful artifact still fails if the regenerated source drifts away from the locked capture.

The parity evaluator should check:
- Visual similarity for rendered evidence.
- Token-family presence.
- Source artifact consistency.
- Extension-axis evidence.
- Anti-pattern divergence.
- Required anchor count.
- Required revision count.

Manual review is allowed only for fields that the replay contract marks unsupported.
Manual review must still write a concrete finding, not a pass-by-opinion note.

When parity fails, fix the source artifact or amend the Visual Specification.
Do not update the locked PNG after implementation work starts unless the Visual Specification amendment flow approves it.

Parity reports should expose raw metric values.
A pass/fail label without measured SSIM, pHash, token presence, count, or manual-review finding is insufficient.
When a metric is not applicable, the report should say which replay-contract clause made it not applicable.

Token parity should compare family names first and individual token names second.
A payload with correct family names but anonymous or renamed values is not enough for build enforcement.

## Runtime check methodology

Runtime checks use `frame_strip_and_audio_waveform_export`.
Runtime evidence must map implementation outputs back to locked anchors.

Runtime checks enabled by this plugin: frame_motion, timeline_order, audio_presence, type_legibility.

The runtime packet must include:
- Runtime screenshots, renders, frames, pages, or chart PNGs for every locked anchor.
- A route, slide number, camera name, frame index, document page, or game state mapping.
- Token presence evidence from source or built artifacts.
- Notes about unsupported toolchain variance.
- A pass/fail summary for every medium-specific check.

Runtime checks reject:
- Missing anchor mappings.
- Untokenized visual values.
- Source-tool default styling that was not present in the locked mockup.
- Axis drift toward an adjacent preset or generic template.
- Loss of project-specific content.
- Missing accessibility or legibility evidence where the medium requires it.

Runtime evidence should be captured from the same operating context users will see.
Do not substitute a design-tool preview when the deliverable is an engine runtime, a simulator runtime, a browser deck, a PDF export, or a rendered chart.

If runtime cannot match the locked mockup because the product requirements changed, open a Visual Specification amendment.

Runtime evidence should not be captured from a development-only debug view unless the final deliverable is that debug view.
Turn off inspector overlays, selection outlines, debug bounds, and capture widgets before recording evidence.
If a runtime engine has nondeterministic lighting, particles, physics, data, or animation, capture enough frames or seeds to make the comparison fair.

## Anti-pattern catalog

The following anti-patterns apply to this medium before project-specific anti-patterns are added:

- Tool-default output that preserves the source application's sample style.
- Generic layout with no project-specific entities, states, or evidence.
- Token payload written by hand when structured source was available.
- One-note palette that ignores semantic state or hierarchy.
- Typography that does not fit the medium's reading distance or interaction context.
- Equal-weight regions when the locked anchor declares a primary region.
- Decorative complexity that reduces usability, legibility, or narrative clarity.
- Claims of platform idiom, story, brand, motion, realism, pagination, game readability, or chart rigor without measurable evidence.
- Screenshot-only source with no editable artifact when the medium has a structured source format.
- A single composition repeated across every anchor.

Medium-specific reject examples:
- Video Animation anchors that ignore `pacing_register`.
- Missing any token family from: frame_pacing, motion_curve, type_in_motion, audio_bed, color_grade, transition_vocab.
- Fewer than 3 anchor mockups or fewer than three captured revisions per anchor.
- Locked evidence that cannot be regenerated or reviewed from source.
- Reference captures that are actually anti-patterns copied into the final direction.

The reviewer should add project-specific anti-pattern PNGs, frames, pages, or charts whenever the brief names a style to avoid.
Those anti-patterns become part of the runtime pHash or manual divergence packet.

Anti-patterns must be stored as evidence, not merely named in prose.
When the anti-pattern is conceptual, create a small reference note explaining what visible feature should be rejected.
When the anti-pattern is a public reference, keep URL, timestamp, and capture dimensions.

## Build-agent gospel template

The build-agent gospel template for this medium is `skills/templates/gospel-video_animation.md`.
The orchestrator prepends that template to build tickets after the Visual Specification gate passes.

The gospel tells implementers how to:
- Load locked anchors.
- Preserve token names.
- Reject unmanifested values.
- Map runtime outputs to anchors.
- Respect the universal axes and medium extension axis.
- Stop and request an amendment when the contract is incomplete.

The gospel is intentionally stricter than normal implementation guidance.
It exists because build agents otherwise fill gaps with generic defaults from frameworks, render engines, deck tools, or chart libraries.

If a project has an implementation framework with a stricter existing token convention, the build agent may adapt token names only if the original manifest paths remain discoverable in source.

The gospel is injected after the medium is selected.
If the executor prompt does not include the gospel, the build ticket is incomplete and should not start.
This is a mechanical safety rule, not a preference.

## Token family details

Token families define the medium-specific visual contract. Each family must be present in the payload.

### frame_pacing

`frame_pacing` controls frame pacing decisions for video_animation.
It must be extracted from the locked source artifact whenever Lottie JSON or an equivalent structured format is available.
The family should include named values rather than anonymous measurements whenever the source format provides names.
The build agent must use these values instead of tool defaults.
The runtime gate may inspect source, rendered evidence, and manifest tokens to confirm the family survived implementation.
If `frame_pacing` is missing, the Visual Specification is incomplete for this medium.
Example evidence includes a source token, rendered measurement, reviewer note, and manifest JSON entry.

### motion_curve

`motion_curve` controls motion curve decisions for video_animation.
It must be extracted from the locked source artifact whenever Lottie JSON or an equivalent structured format is available.
The family should include named values rather than anonymous measurements whenever the source format provides names.
The build agent must use these values instead of tool defaults.
The runtime gate may inspect source, rendered evidence, and manifest tokens to confirm the family survived implementation.
If `motion_curve` is missing, the Visual Specification is incomplete for this medium.
Example evidence includes a source token, rendered measurement, reviewer note, and manifest JSON entry.

### type_in_motion

`type_in_motion` controls type in motion decisions for video_animation.
It must be extracted from the locked source artifact whenever Lottie JSON or an equivalent structured format is available.
The family should include named values rather than anonymous measurements whenever the source format provides names.
The build agent must use these values instead of tool defaults.
The runtime gate may inspect source, rendered evidence, and manifest tokens to confirm the family survived implementation.
If `type_in_motion` is missing, the Visual Specification is incomplete for this medium.
Example evidence includes a source token, rendered measurement, reviewer note, and manifest JSON entry.

### audio_bed

`audio_bed` controls audio bed decisions for video_animation.
It must be extracted from the locked source artifact whenever Lottie JSON or an equivalent structured format is available.
The family should include named values rather than anonymous measurements whenever the source format provides names.
The build agent must use these values instead of tool defaults.
The runtime gate may inspect source, rendered evidence, and manifest tokens to confirm the family survived implementation.
If `audio_bed` is missing, the Visual Specification is incomplete for this medium.
Example evidence includes a source token, rendered measurement, reviewer note, and manifest JSON entry.

### color_grade

`color_grade` controls color grade decisions for video_animation.
It must be extracted from the locked source artifact whenever Lottie JSON or an equivalent structured format is available.
The family should include named values rather than anonymous measurements whenever the source format provides names.
The build agent must use these values instead of tool defaults.
The runtime gate may inspect source, rendered evidence, and manifest tokens to confirm the family survived implementation.
If `color_grade` is missing, the Visual Specification is incomplete for this medium.
Example evidence includes a source token, rendered measurement, reviewer note, and manifest JSON entry.

### transition_vocab

`transition_vocab` controls transition vocab decisions for video_animation.
It must be extracted from the locked source artifact whenever Lottie JSON or an equivalent structured format is available.
The family should include named values rather than anonymous measurements whenever the source format provides names.
The build agent must use these values instead of tool defaults.
The runtime gate may inspect source, rendered evidence, and manifest tokens to confirm the family survived implementation.
If `transition_vocab` is missing, the Visual Specification is incomplete for this medium.
Example evidence includes a source token, rendered measurement, reviewer note, and manifest JSON entry.

## Reference capture rules

Reference capture must match the medium.
Use the same class of artifact the final deliverable will use whenever possible.

For video_animation, preferred reference formats are: Lottie JSON, Rive timeline JSON, After Effects bodymovin JSON, timeline JSON, frame-strip PNGs.

Reference capture rules:
- Capture references at comparable aspect ratio, page size, frame size, device class, camera angle, or chart dimensions.
- Store references in `visual-references/references/` with stable filenames.
- Store anti-patterns in `visual-references/anti-patterns/`.
- Record source URL, file path, capture command, viewport, frame index, page number, or export settings.
- Avoid references that cannot legally or practically be inspected by the reviewer.
- Prefer current, concrete artifacts over mood words.

References are not copied.
They are used to define contrast, hierarchy, craft expectations, and anti-pattern boundaries.
The locked mockup must still express the actual project content.

When references are screenshots from native apps, games, render engines, or deck tools, record OS, app version, engine version, or renderer settings if known.
When references are public web captures, include the capture timestamp and viewport.
When references are operator-supplied files, include the file hash or stable path.

## Mockup format details

Mockup format: `frame_strip_pngs_plus_audio_waveform_plus_timeline_json`.

A complete locked mockup packet contains:
- Source artifact.
- Rendered visual evidence.
- Token payload.
- Iteration log.
- Reference and anti-pattern links.
- Manifest entries mapping anchor names to files.

Anchor slugs must be lowercase and stable.
Use names that describe the state or view, not generic numbers.
Good slugs name things like `default`, `settings`, `title`, `content`, `wordmark`, `hero`, `hud`, `scatter`, or `body-spread` when those are the actual anchors.

Required locked naming pattern:
- `mockups/locked-{anchor}.png` for visual evidence.
- `mockups/locked-{anchor}.json` when the source format is JSON.
- `mockups/locked-{anchor}.html`, `.pptx`, `.css`, `.tex`, `.svg`, `.tscn`, `.prefab`, or engine-specific source where applicable.

The manifest should include capture dimensions and source type.
If the medium needs multiple files for one anchor, the manifest should list a source bundle rather than forcing one filename to carry all meaning.

The mockup packet fails if any locked anchor cannot be tied back to a source artifact.
It also fails if a source artifact is present but the rendered evidence is stale or belongs to a previous revision.

Mockup packet audit questions:
- Can another agent open or parse the source artifact?
- Can another agent identify which render corresponds to which source revision?
- Can another agent rerun token extraction without hidden manual state?
- Can another agent see why the locked version beat the previous revision?
- Can another agent map the locked anchor to the runtime implementation target?
- Can another agent determine whether deterministic replay is supported?

## Adjudication question set (medium-specific extensions)

Reviewers answer the universal Visual Specification questions first.
Then they answer these medium-specific questions:

1. Does every anchor prove the declared `pacing_register` value with concrete visual evidence?
2. Are all required token families present: frame_pacing, motion_curve, type_in_motion, audio_bed, color_grade, transition_vocab?
3. Are there at least 3 anchors and three captured revisions per anchor?
4. Does the source format allow the build agent to implement without inventing missing visual values?
5. Does the locked evidence avoid tool-default or template-default aesthetics?
6. Are references and anti-patterns specific to this medium rather than borrowed from web UI by habit?
7. Would a runtime gate know exactly what to capture and compare?
8. If deterministic replay is unsupported, is operator review explicitly recorded?

The first adjudication round must be revise unless the project already has prior approved locked artifacts for the same medium.
A revise finding should name concrete changes tied to tokens, anchors, axes, or references.
Approval without evidence does not satisfy this plugin.

## Validation history

Version 1.0:
- Created for Batch 14 of the Visual Specification System.
- Defines the video_animation medium plugin frontmatter contract.
- Adds token extraction through `scripts/extract_tokens_from_video_animation.py`.
- Adds gospel template `skills/templates/gospel-video_animation.md`.
- Declares regression replay support as `timeline non-deterministic without source files`.
- Validates against `schemas/medium-plugin.schema.json`.

Future versions should update this history when token families, replay support, thresholds, or mockup formats change.
