=== VISUAL SPECIFICATION CONTRACT (web_ui) ===

You are building UI under a Visual Specification.

VS path: {visual_spec_path}
References dir: {visual_spec_references_dir}
Locked anchor mockups (you must structurally match these for their respective screens):
{list of anchor mockup HTML paths}
Aesthetic preset: {visual_quality_target_preset}
Axes: density={density}, topology={topology}, expressiveness={expressiveness}, motion={motion}, platform={platform}, trust={trust}
Adversarial pass argued for: {adjacent_preset_rejected} - DO NOT drift toward this aesthetic.

LOAD-BEARING REQUIREMENTS:
1. Open the VS, read it in full, and load every locked mockup HTML before writing code.
2. Use ONLY token values from VS section 4 / manifest.json. Do not invent colors, sizes, radii, motion durations, spacing, focus geometry, or elevation.
3. Implement the design tokens as CSS variables (or framework equivalent) using the EXACT names from manifest.tokens. The runtime gate will fail your work if it cannot grep the runtime for token names matching the manifest.
4. For each component you build, write a comment block at the top of the component file citing which tokens you used.
5. If you need a token that is not listed, STOP. Do NOT synthesize a value. Create a VS amendment ticket.
6. At every phase gate, take screenshots and verify they match the locked mockups via SSIM (>=0.85 against locked-{screen}.png) for the corresponding screens.
7. The runtime layout topology must match the locked mockup's element structure within +/-20% (header/aside/nav/main/section counts).
8. The runtime PNG must have pHash distance > 12 from each anti-pattern PNG.
9. Read the iteration log to understand WHY the locked mockup looks the way it does. Do not regress to earlier revisions.
10. The runtime must pass the brief specificity contract: >=80% of declared `domain_entities`, >=5 of declared `workflow_signatures`, declared `brand_or_context_invariants` all present, >=3 of declared `signature_affordances`, NO declared `forbidden_generic_signals`.
11. The visual reviewer is the authority on aesthetic. The mechanical gate is the authority on structure, tokens, contrast, and provenance.

REJECT (these will fail visual gate):
- Generic SaaS card grid (4+ equal-weight cards in flat grid)
- Drift toward {adjacent_preset_rejected}
- Tokens with no manifest provenance (inline-style hex literals not in manifest)
- Layout topology that diverges >20% from locked mockups
- Bootstrap default form styling
- Default browser focus rings
- "Welcome [Name]" header greeting
- Quick Actions generic sidebar

REJECT specifically per declared aesthetic axes:
- if density: dense - row heights >32pt, section gaps >24pt, fewer than declared rows visible at 800pt content height
- if topology: list-detail - equal-weight 50/50 panes
- if expressiveness: restrained - multiple competing accent colors, bold gradients
- if motion: calm - bouncy easing, focus durations >120ms, expressive transitions
- if trust: enterprise - playful illustrations, casual copy, missing compliance badges where the brief requires them

Before implementation:
- Locate `manifest.json`.
- Locate every locked anchor HTML file.
- Locate every locked anchor PNG file.
- Locate `iteration-log.md`.
- Locate the reference captures and anti-pattern captures.
- Confirm the route or screen each anchor maps to in the runtime.
- Confirm whether the implementation framework supports preserving CSS variable names.
- Confirm how screenshots will be taken for the runtime gate.

Token implementation rules:
- Use CSS variables named from manifest token paths, such as `--color-surface`, `--type-body-size`, `--spacing-base`, and `--radius-standard`, unless the repository already has a stricter token naming convention.
- Preserve the manifest token name in source even when the framework compiles values.
- Prefer token references over literal values in component code.
- Literal values are allowed only inside the token definition layer.
- Do not create local component-only colors.
- Do not create one-off spacing values.
- Do not create one-off border radii.
- Do not create one-off transition durations.
- Do not use `box-shadow` values that are not represented by elevation tokens.
- Do not use browser default outlines.

Component comment rule:
- At the top of every component file that implements visual UI, include a short comment block.
- The comment block must list the token families used by that file.
- The comment block must cite exact token names.
- Keep the block factual and short.
- Do not describe the product or implementation plan in that block.

Example comment shape:
```css
/*
VS tokens:
color.surface, color.surface-elevated, color.border, color.text-primary, color.accent
type.body, type.caption, spacing.scale, radius.standard, focus.offset
*/
```

Allowed implementation approaches:
- Plain CSS.
- CSS Modules.
- CSS-in-JS if token names remain discoverable.
- Tailwind only if the project already uses it and config maps exact manifest tokens.
- Design-system components only if they can be configured to exact manifest tokens.

Disallowed implementation shortcuts:
- Importing Bootstrap or Material defaults.
- Importing an unrelated dashboard template.
- Using a component library default theme as the design.
- Letting chart or table libraries control typography and color without token overrides.
- Replacing locked data structures with generic cards.
- Adding a marketing hero before the operator workflow.
- Adding ornamental gradients or blobs to make a dashboard feel designed.
- Hiding missing specificity behind placeholders.

Layout topology rules:
- Match the locked anchor's region hierarchy first.
- Preserve the primary region's visual priority.
- Preserve list/detail pane dominance.
- Preserve multi-region grid relationships.
- Preserve nav/header/action affordance placement unless the VS explicitly allows responsive variation.
- Do not turn a list/detail anchor into a card grid.
- Do not make panes equal-weight when the locked mockup makes one region primary.
- Do not collapse dense dashboard structure into a landing-page composition.
- At runtime, countable semantic regions must remain within +/-20% of the locked HTML.

Density rules:
- Dense means repeated information is visible and scannable.
- Balanced means there is room for grouping but still meaningful simultaneous information.
- Sparse means the page is intentionally focused and should not fake density with empty cards.
- For dense row-based UI, preserve row height discipline from the locked mockup.
- Do not add extra top padding, oversized headings, large cards, or decorative summaries that reduce visible rows below the declared density.
- Do not hide core data behind tabs, accordions, or modals unless the locked mockup does.

Typography rules:
- Use the exact family stack from manifest tokens.
- Use exact sizes, weights, leading, and tracking from manifest tokens.
- Keep heading scale appropriate to the surface. Operator tools do not get hero-scale headings unless the locked mockup does.
- Prevent awkward line breaks at 1440 by 900.
- Prevent clipped table text and clipped button text.
- Preserve metadata hierarchy.
- Preserve code, numeric, or tabular conventions where the VS declares them.

Color rules:
- Use exact color tokens from manifest.
- State colors must map to semantic tokens.
- Accent is not a generic blue permission slip.
- Danger, warning, and success must not rely on color alone when the workflow has risk.
- If a chart library creates colors, override them with manifest tokens or VS-approved chart tokens.
- Do not use inline hex literals outside token definitions.
- Do not add alpha variants unless they are tokenized or explicitly derivable in the VS.

Focus and interaction rules:
- Implement visible focus for every interactive element.
- Use manifest focus geometry.
- Use tokenized focus color, offset, and radius.
- Preserve hover, pressed, selected, disabled, loading, empty, and error states implied by the locked mockup.
- Do not rely on browser default focus rings.
- Do not remove outlines without replacing them.
- Respect reduced-motion preferences.

Motion rules:
- Use exact manifest durations and easing.
- For calm or restrained surfaces, keep motion functional.
- For dense operator tools, avoid decorative looped motion.
- For expressive or marketing surfaces, keep choreography tied to the locked mockup and references.
- Do not add bouncy easing unless the VS declares it.
- Do not use long focus or state transitions that slow repeated work.

Data specificity rules:
- Use realistic domain data.
- Preserve named entities from the VS.
- Preserve workflow signatures.
- Preserve brand or context invariants.
- Preserve signature affordances.
- Remove forbidden generic signals.
- Do not replace realistic data with lorem ipsum, "Project Alpha", "Acme", generic percentages, or fake placeholder teams unless the VS uses those exact terms.

Marketing surface rules:
- The brand, product, person, place, or object must be a first-viewport signal.
- The first viewport must reveal actual product, state, proof, or object of interest.
- Do not hide the product behind abstract gradients.
- Do not use a split text/media hero unless the locked mockup does.
- Do not wrap hero content in a generic card unless the locked mockup does.
- Keep the next section hinted in the first viewport when the VS requires public-page behavior.

Dashboard and operator surface rules:
- Prioritize scan speed.
- Prioritize selected state.
- Prioritize table/list rhythm.
- Prioritize filter and scope visibility.
- Prioritize source, timestamp, status, and ownership metadata.
- Avoid greetings.
- Avoid Quick Actions sidebars.
- Avoid decorative KPI grids that are not part of the workflow.
- Avoid huge empty-state-style panels when data should be present.

Chart and table rules:
- Preserve axis, unit, source, and time range where shown.
- Preserve row counts and column hierarchy.
- Preserve sorting, filtering, and selection affordances where shown.
- Override third-party default colors and fonts.
- Use tabular numeric settings when manifest typography or local design system provides them.
- Do not add unexplained chart color palettes.

Responsive behavior:
- The locked 1440 by 900 anchor is authoritative.
- Responsive changes may be implemented only after the desktop anchor matches.
- Mobile or tablet adaptations must preserve token provenance.
- Responsive variants must preserve the same workflow priority.
- Do not use mobile simplification to erase required entities, workflow signatures, or affordances.

Verification:
- Capture runtime screenshots for each anchor route.
- Compare against locked PNGs with SSIM.
- Inspect DOM topology counts.
- Grep source and built CSS for manifest token names.
- Compute pHash distance against anti-patterns.
- Run contrast checks where the repo provides them.
- Record evidence in the expected gate artifact.

When a mismatch appears:
- If the implementation diverged, fix implementation.
- If the locked mockup is impossible to implement as specified, create a VS amendment ticket.
- If the product requirement changed, create a VS amendment ticket.
- If a token is missing, create a VS amendment ticket.
- Do not silently edit the manifest or locked mockup from build-agent code.

Final acceptance checklist:
- Every component file cites tokens.
- Runtime screenshots exist for every locked anchor.
- SSIM >=0.85 for each runtime screenshot.
- Topology variance <=20%.
- Token presence >=80%.
- pHash distance >12 from anti-pattern captures.
- Brief specificity contract passes.
- No forbidden generic signals remain.
- No unmanifested colors, spacing, radii, motion, elevation, or focus values remain.
- Reviewer can trace visible UI decisions back to the locked mockup, manifest, iteration log, or VS.

=== END CONTRACT ===
