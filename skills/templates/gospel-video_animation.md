=== VISUAL SPECIFICATION CONTRACT (video_animation) ===

You are building under a medium-specific Visual Specification.

VS path: {visual_spec_path}
References dir: {visual_spec_references_dir}
Locked anchors: {list_of_anchor_paths}
Aesthetic preset: {visual_quality_target_preset}
Axes: density={density}, topology={topology}, expressiveness={expressiveness}, motion={motion}, platform={platform}, trust={trust}
Medium extension axis: pacing_register={pacing_register}
Adversarial pass argued for: {adjacent_preset_rejected} - do not drift toward that adjacent aesthetic.

LOAD-BEARING REQUIREMENTS:
1. Read the Visual Specification, manifest, iteration log, and every locked anchor before editing implementation files.
2. Use only token values from the manifest token payload.
3. Preserve token names or manifest paths in source so the runtime gate can find them.
4. Map each runtime screen, slide, page, frame, shot, chart, or game state to a locked anchor.
5. Stop and create a Visual Specification amendment when a needed value is missing.
6. Capture runtime evidence in the medium's required format before claiming parity.
7. Do not silently replace the medium artifact with an easier web-style approximation.

TOKEN FAMILIES:
- `frame_pacing` must be implemented from manifest tokens.
- `motion_curve` must be implemented from manifest tokens.
- `type_in_motion` must be implemented from manifest tokens.
- `audio_bed` must be implemented from manifest tokens.
- `color_grade` must be implemented from manifest tokens.
- `transition_vocab` must be implemented from manifest tokens.

REJECT:
- Untokenized colors, sizes, spacing, motion, lighting, chart colors, page margins, or state encodings.
- Source-tool defaults that were not present in the locked mockup.
- Generic placeholder content replacing declared domain entities or evidence.
- Layout, scene, page, frame, chart, or HUD topology that no longer matches the locked anchor.
- Missing runtime capture for any locked anchor.
- Any implementation that cannot explain which token family controls a visible decision.

REJECT BY AXIS:
- If density is dense, preserve visible information density and do not inflate whitespace.
- If density is sparse, do not fake sophistication with empty repeated containers.
- If topology is list_detail or multi_region, preserve primary and secondary region hierarchy.
- If topology is narrative_sequence, preserve order, transitions, and repeated motifs.
- If expressiveness is restrained or quiet, remove decorative effects not in the manifest.
- If expressiveness is playful or cinematic, keep expressiveness tied to locked evidence instead of generic animation.
- If motion is static or subtle, avoid bouncy or long decorative motion.
- If motion is rapid or cinematic, preserve pacing tokens and legibility under motion.
- If trust is enterprise, financial, clinical, regulated, or safety_critical, preserve explicit labels, states, and source context.
- If trust is approachable or luxury, preserve polish without losing clarity or accessibility.
- If pacing_register is set, preserve its medium-specific idiom in every runtime artifact.

BEFORE IMPLEMENTATION:
- Locate `manifest.json`.
- Locate the token payload JSON.
- Locate every locked source artifact.
- Locate every locked rendered evidence artifact.
- Locate reference captures and anti-pattern captures.
- Identify the runtime output for each locked anchor.
- Confirm the implementation stack can preserve token provenance.
- Confirm how screenshots, renders, pages, frames, or charts will be captured.

IMPLEMENTATION RULES:
- Define a token layer first.
- Keep literal values inside that token layer only.
- Cite token families in component, scene, slide, page, chart, timeline, or style files.
- Override library defaults with manifest tokens.
- Preserve source order and hierarchy from locked anchors.
- Preserve selected, active, disabled, focus, loading, warning, destructive, and empty states when the anchor includes them.
- Respect reduced-motion or accessibility settings where the medium supports them.
- Keep text legible at the medium's actual reading distance.
- Keep charts, marks, logos, or HUD elements readable at their smallest declared size.

SOURCE ARTIFACT RULES:
- Keep editable source artifacts in the repository or project artifact bundle.
- Keep rendered evidence next to the source artifact or linked from the manifest.
- Do not regenerate locked evidence with different export settings unless the VS amendment records the change.
- Preserve source filenames enough that the reviewer can map them back to anchor slugs.
- Preserve renderer, simulator, deck, engine, chart, or PDF settings used for capture.
- Preserve any seed, frame number, slide number, camera name, page number, or state name needed for repeat capture.
- When the medium uses binary source, export a sidecar text or JSON summary when the tool supports it.
- When the medium uses manual JSON, validate it before implementation begins.

TOKEN PROVENANCE RULES:
- Prefer source token names over inferred names.
- Preserve manifest token paths in comments or token maps.
- Do not rename token families.
- Do not collapse multiple semantic colors into one generic color.
- Do not collapse multiple type levels into one text style.
- Do not collapse motion, lighting, page, chart, HUD, or lockup values into prose.
- Do not let an implementation library silently map tokens to its default theme.

COMMENT BLOCK SHAPE:
```
VS tokens:
token.family.name, token.family.name
Locked anchors:
locked-anchor-name
```

MEDIUM-SPECIFIC RULES:
- Preserve `frame_pacing` values exactly unless a Visual Specification amendment changes them.
- Preserve `motion_curve` values exactly unless a Visual Specification amendment changes them.
- Preserve `type_in_motion` values exactly unless a Visual Specification amendment changes them.
- Preserve `audio_bed` values exactly unless a Visual Specification amendment changes them.
- Preserve `color_grade` values exactly unless a Visual Specification amendment changes them.
- Preserve `transition_vocab` values exactly unless a Visual Specification amendment changes them.
- Keep export dimensions, safe areas, camera names, slide numbers, page sizes, frame indices, or chart dimensions aligned with the manifest.
- Do not substitute a screenshot where structured source is required.
- Do not modify locked mockups from build code.
- Do not invent a missing token by sampling a PNG.
- Do not collapse multiple anchors into one generic runtime route.

VERIFICATION:
- Capture runtime evidence for every locked anchor.
- Compare rendered evidence against the locked PNG or frame.
- Inspect source for token names.
- Check anti-pattern divergence.
- Verify accessibility or legibility requirements for this medium.
- Record evidence in the expected gate artifact.

WHEN A MISMATCH APPEARS:
- If implementation drifted, fix implementation.
- If the locked mockup is impossible to implement, create a Visual Specification amendment.
- If requirements changed, create a Visual Specification amendment.
- If a token is missing, create a Visual Specification amendment.
- If a source tool is unavailable, record the blocker and use the plugin's unsupported behavior.

FINAL ACCEPTANCE CHECKLIST:
- All token families are represented.
- All anchors have runtime evidence.
- Runtime evidence is mapped to locked anchors.
- Source contains manifest token names or paths.
- No unmanifested visual values remain.
- No forbidden generic signals remain.
- Extension-axis idiom is visible.
- Reviewer can trace visible decisions to the VS, manifest, references, iteration log, or locked mockup.

HANDOFF NOTE:
- If you cannot complete one checklist item, report the exact missing artifact or token.
- Do not substitute a general design judgment for missing evidence.
- Do not ask the reviewer to trust the runtime by inspection when the plugin defines a mechanical check.
- Do not continue into feature work while the visual contract is unresolved.

=== END CONTRACT ===
