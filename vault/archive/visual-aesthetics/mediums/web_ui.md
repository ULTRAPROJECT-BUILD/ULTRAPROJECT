---
type: medium-plugin
medium: web_ui
version: "1.0"
applicable_aesthetic_axes:
  density: [sparse, balanced, dense]
  topology: [single_panel, list_detail, multi_region]
  expressiveness: [restrained, editorial, expressive, playful]
  motion: [static, subtle, functional, expressive]
  platform: [web_native]
  trust: [approachable, professional, enterprise, financial, luxury]
medium_extension_axes: {}
mockup_format: html_css
mockup_anchor_count_min: 2
mockup_revisions_per_anchor_min: 3
token_families: [color, type, spacing, radius, elevation, motion, density, focus]
token_extractor_script: scripts/extract_tokens_from_web_ui.py
parity_methodology:
  method: mixed
  renderer_script: scripts/regen_mockup.py
  comparison_metrics: [ssim, element_tree, css_token_ast]
  thresholds:
    ssim_regen_min: 0.92
    topology_variance_max_pct: 20
    css_token_ast_match: 1
  required_artifacts: [html, css, png, manifest]
runtime_check_methodology:
  capture_method: headless_chromium_standard_viewport
  checks: [ssim_runtime, layout_topology, token_presence, antipattern_phash]
  budgets:
    capture_seconds: 20
    token_walk_seconds: 20
gospel_template_path: skills/templates/gospel-web_ui.md
applicable_presets: [operator_triage, operator_admin, observability_console, executive_analytics, developer_tools, apple_consumer, vercel_marketing, editorial_premium, fintech_precise, playful_consumer, data_scientific]
regression_replay_contract:
  supported: true
  renderer_script: scripts/regen_mockup.py
  required_source_artifacts: [html, css]
  supported_token_mutations: ["color.*", "spacing.*", "radius.*", "type.*", "elevation.*", "motion.*", "focus.*"]
  unsupported_token_mutations: []
  unsupported_mutation_behavior: skip
  replay_fixture: tests/fixtures/replay-web_ui/
  replay_determinism_test: tests/test_replay_deterministic_web_ui.py
---

# web_ui Medium Plugin

## Overview

Web user interfaces are any deliverables rendered in a browser.

This includes dashboards, operator consoles, web applications, marketing sites,
e-commerce flows, portfolios, developer tools, admin systems, content sites,
embedded browser tools, and web-native prototypes that are intended to become
production UI.

This excludes native mobile and desktop apps, which use `native_ui`;
presentations, which use `presentation`; standalone charts, which use
`data_visualization`; game HUDs, which use `game_ui`; and pure document layout,
which uses `document_typography`.

The medium exists because browser UI has a specific failure mode: it is easy for
an agent to produce plausible-looking generic SaaS surfaces that do not preserve
the locked visual specification. This plugin converts visual work into
browser-native artifacts, extracts CSS tokens, and gives runtime gates concrete
ways to reject drift.

This plugin is the first priority medium because dashboards and operator tools
are a common pain point. Dense web UI work needs precise typography, real data,
durable layout topology, disciplined spacing, obvious state, and token
provenance. The goal is not a pretty mockup. The goal is a visual contract the
build agent can implement without improvising.

Schema note: repository schemas currently use canonical enum names such as
`single_panel`, `list_detail`, `multi_region`, `web_native`, `subtle`, and
`functional`. Human-facing documents may still describe the same concepts as
single-pane, list-detail, multi-region, web-app, calm, and standard when quoting
brief language or reviewer questions.

## Stage A operation (Scaffold)

Stage A creates rough, hand-coded browser mockups for at least two anchor
screens. The scaffold exists to find the right structure before polish.

The scaffold must be self-contained HTML and CSS. Do not use a framework,
component library, bundled JavaScript, external fonts, remote images, npm
packages, CSS resets, Tailwind, Bootstrap, Material, shadcn, Radix, or copied
production source code.

Allowed scaffold ingredients:

- Plain `.html` files.
- Inline `<style>` block CSS.
- Relative linked CSS only when the CSS file is part of the mockup artifact.
- Static semantic HTML.
- Realistic sample data for the product domain.
- Simple geometric marks, initials, or solid blocks when imagery is not central.
- Embedded data URLs if an image is necessary.

Required anchor count:

- Create at least two anchor screens.
- One anchor should represent the primary workflow.
- One anchor should represent the most structurally different screen or state.
- For dashboards, prefer one high-throughput list, table, or console screen and
  one detail, configuration, incident, report, or secondary analytical screen.
- For marketing sites, prefer first viewport plus one conversion or proof screen.

Required scaffold naming:

- `mockups/scaffold-1-{anchor}-rev1.html`
- `mockups/scaffold-1-{anchor}-rev1.png`
- `mockups/scaffold-2-{anchor}-rev1.html`
- `mockups/scaffold-2-{anchor}-rev1.png`

Use lowercase anchor slugs. Use names that identify the workflow, such as
`triage-queue`, `incident-detail`, `admin-users`, `billing-risk`, `overview`,
`pricing`, or `conversion`.

Capture every scaffold at a 1440 by 900 viewport using `scripts/regen_mockup.py`.
The renderer must run from the repository root so relative paths and artifact
references are stable.

The initial scaffold should resolve:

- Dominant topology.
- Pane ratios.
- Header, navigation, and action regions.
- Primary data density.
- Type scale posture.
- Interaction affordance placement.
- State color vocabulary.
- Surface hierarchy.
- Border and separator rhythm.
- Whether the screen is actually usable at 1440 by 900.

The initial scaffold may be visually rough. It may use approximate colors,
placeholder radius, provisional spacing, and incomplete state treatment. It may
not use lorem ipsum, generic dashboards, fake empty cards, or decorative filler
that will not exist in the product.

For operator and dashboard work, populate the scaffold with realistic records:

- Names that match the domain.
- Statuses with meaningful severity or lifecycle state.
- Timestamps and metadata that imply workflow urgency.
- Table/list rows long enough to test truncation.
- Filters that match the task.
- Selected row or active detail state.
- Disabled, danger, and secondary action states where relevant.

For marketing work, populate the scaffold with real product language from the
brief:

- Product name or category must be visible in the first viewport.
- The primary claim must be literal, not vague.
- Proof, customer, artifact, or feature evidence must appear above or near the
  fold.
- Avoid split-card hero defaults unless the reference explicitly requires it.

Before leaving Stage A, write a short `iteration-log.md` entry for each anchor:

- Anchor name.
- Source file.
- PNG file.
- Declared axes.
- What the scaffold is trying to test.
- Known weaknesses to improve in Stage B.

## Stage B operation (Iterate)

Stage B converts rough scaffolds into locked visual anchors through deliberate
revision. Each anchor requires at least three captured revisions before locking.

Every revision cycle follows the same loop:

1. Capture the current HTML as PNG at 1440 by 900.
2. Compare it to the selected references and anti-patterns.
3. Identify at least three concrete visual deltas.
4. Revise the HTML/CSS.
5. Capture again.
6. Append a diff summary to `iteration-log.md`.

The deltas must be specific enough for another agent to audit. Avoid phrases
like "make it cleaner" or "more premium." Use concrete observations instead:

- "The list/detail panes are nearly equal weight; increase list dominance to
  make the triage workflow read first."
- "Primary text and secondary metadata are too similar; reduce metadata weight
  and color contrast while preserving AA."
- "Every panel has the same radius and shadow; remove low-value shadows and use
  separators for dense table structure."
- "The button accent is generic blue and has no pressed state; derive hover and
  pressed from the selected accent token."
- "The table row height only fits 14 records at 800pt; tighten vertical padding
  to support the dense claim."

Revision naming:

- `mockups/iter-1-{anchor}-rev1.html`
- `mockups/iter-1-{anchor}-rev1.png`
- `mockups/iter-1-{anchor}-rev2.html`
- `mockups/iter-1-{anchor}-rev2.png`
- `mockups/iter-1-{anchor}-rev3.html`
- `mockups/iter-1-{anchor}-rev3.png`

If Stage A files are already revision 1, Stage B may continue numbering from
`rev2`. The final locked artifact still gets its own name.

Each revision must preserve:

- Self-contained HTML.
- No external CSS or JavaScript dependencies.
- Real data.
- Declared topology.
- Anchor role.
- Viewport capture size.
- Provenance from references and brief.

Each revision should improve at least one of:

- Topology clarity.
- Text hierarchy.
- Data density.
- Action hierarchy.
- State communication.
- Surface material.
- Focus and keyboard affordance.
- Brand or domain specificity.
- Anti-pattern distance.

Do not lock a mockup because it looks acceptable in isolation. Lock it only when
the iteration log explains why the chosen revision is better than the earlier
ones and why it resists the adjacent rejected preset.

The locked files are:

- `mockups/locked-{anchor}.html`
- `mockups/locked-{anchor}.png`

The locked HTML is the source of truth for token extraction and structural
comparison. The locked PNG is the visual source of truth for SSIM comparison.

## Stage E operation (Token extraction)

Stage E converts the locked HTML/CSS into a web UI token payload.

Run the extractor from the repository root:

```bash
python3 scripts/extract_tokens_from_web_ui.py \
  --mockup mockups/locked-{anchor}.html \
  --out extracted-tokens-draft.json
```

The extractor reads:

- Inline `<style>` blocks.
- Relative linked stylesheets.
- Inline `style` attributes.
- Selectors and declarations through a CSS parser.
- HTML row/list elements for density proxy signals.

The extractor emits a draft payload matching
`schemas/token-payload-web_ui.schema.json`.

The draft is not automatically final. Review it before adding it to
`manifest.json`.

Review requirements:

- Rename tokens semantically when the heuristic name is too generic.
- Consolidate near-duplicate colors where Delta E76 is under 3.
- Preserve only tokens that are visually present in the locked mockup or are
  required by the schema for runtime gates.
- Add justifications for chosen semantic names in the Visual Specification.
- Explain any required token that is represented by a proxy value because the
  locked mockup did not include that exact state.
- Ensure color values are uppercase six-digit hex.
- Ensure type values are CSS pixel numbers, not raw strings.
- Ensure radius values fit the current web token schema.
- Ensure motion tokens are named timing objects with duration and easing.

For multi-anchor specifications, extract each locked anchor and merge tokens
manually. The merged manifest should not contain duplicate values under
different names unless the names represent genuinely different semantics.

Expected token families:

- `color`
- `type`
- `spacing`
- `radius`
- `elevation`
- `motion`
- `density`
- `focus`

## Parity methodology

Parity answers whether the locked source still regenerates into the locked
visual artifact and whether the implementation preserves the locked visual
contract.

Mockup regeneration parity:

- Render `mockups/locked-{anchor}.html` with headless Chromium.
- Use a 1440 by 900 viewport.
- Disable animations or wait for a stable frame.
- Compare the regenerated PNG to `mockups/locked-{anchor}.png`.
- SSIM must be at least 0.92.
- If SSIM is lower, investigate font loading, viewport mismatch, animation,
  anti-aliasing changes, image drift, or accidental source edits.

Topology parity:

- Count semantic structural elements: `header`, `aside`, `nav`, `main`,
  `section`, `article`, `table`, `tr`, `ul`, `ol`, `li`, `form`, `button`.
- Count major region classes in the locked HTML.
- Element-tree count variance must be no more than 20 percent.
- The checker should fail equal-weight list/detail panes when the declared
  topology is list-detail.
- The checker should fail card-grid drift when the declared topology is
  multi-region or list-detail.

CSS token AST parity:

- Extract color tokens from locked mockup CSS.
- Compare them to `manifest.tokens.color`.
- Manifest color values must match CSS-extracted color tokens exactly unless the
  Visual Specification records a justified proxy token.
- Inline runtime colors not present in the manifest are a gate failure.
- CSS variables should use exact manifest token names.

Required parity evidence:

- Locked HTML SHA256.
- Locked PNG SHA256.
- Regenerated PNG SHA256.
- SSIM score.
- Element topology count summary.
- Token extraction payload.
- Any waivers, if granted.

## Runtime check methodology

After the build agent implements the UI, runtime checks compare the delivered
browser output to the locked mockups.

Runtime capture:

- Launch the runtime app in a browser.
- Navigate to the route corresponding to each locked anchor.
- Set viewport to 1440 by 900.
- Wait for data, fonts, and layout to settle.
- Capture a PNG.
- Store the PNG as gate evidence.

Runtime SSIM:

- Compare each runtime PNG to the corresponding `locked-{screen}.png`.
- Minimum SSIM is 0.85.
- Values below 0.85 require either implementation fixes or a VS amendment.
- Do not waive SSIM for obvious topology, density, or token drift.

Runtime topology:

- Walk the runtime DOM.
- Count major regions and repeated structures.
- Compare to locked HTML counts.
- Layout topology variance must be no more than 20 percent.
- Detect list/detail pane ratios where possible.
- Detect generic equal-weight grids where possible.

Runtime token presence:

- Walk compiled CSS, CSS variables, style attributes, and framework token maps.
- At least 80 percent of manifest tokens must be findable by exact token name or
  literal value.
- Token names are preferred because they prove provenance.
- Literal values alone are acceptable only where the runtime framework cannot
  preserve variable names.

Anti-pattern distance:

- Capture runtime PNG pHash.
- Compare to each web UI anti-pattern PNG.
- pHash distance must be at least 12.
- If a runtime image is too close to an anti-pattern, the reviewer should inspect
  whether the implementation regressed toward generic SaaS defaults.

Brief specificity:

- At least 80 percent of declared `domain_entities` must be present.
- At least 5 declared `workflow_signatures` must be present.
- All declared `brand_or_context_invariants` must be present.
- At least 3 declared `signature_affordances` must be present.
- No declared `forbidden_generic_signals` may be present.

## Anti-pattern catalog

Baseline web UI anti-patterns:

- Generic SaaS card grid: three or more equal-weight cards in a flat grid where
  the workflow needs a primary read.
- Bootstrap-default form styling: unmodified input borders, default spacing,
  generic primary buttons, and no product-specific hierarchy.
- Material Design floating action buttons and ripple behavior when the target is
  not Material.
- "Welcome [Name]" header greeting on operator tools.
- Quick Actions sidebar used as a substitute for real workflow affordances.
- Default browser focus rings such as `outline: 2px solid blue`.
- Generic blue accent `#3B82F6` without brand or domain context.
- Equal-weight 50/50 panes for list-detail topology.
- Soft drop shadow on every card.
- Default Inter or Roboto usage without weight, leading, and hierarchy
  discipline.
- Decorative metric cards that do not answer the user's next decision.
- Dense data tables with no selected, hover, focus, loading, empty, or error
  state.
- Marketing hero composition inside an operator tool.
- Operator workflow hidden below a page-level hero.
- Low-contrast metadata that fails accessibility checks.
- Color-only severity without text, icon, or structural support.
- Chart panels with no axis, source, time range, or unit.
- Fake nav items that do not match the declared product domain.
- Placeholder avatars, initials, or emoji in enterprise tools without a task
  reason.
- Consumer illustration language in regulated or enterprise trust contexts.
- Max-width content wrappers that make dashboards waste horizontal space.
- Full-bleed gradients used as brand substitute.
- Card-in-card section nesting.
- Over-rounded pills used for every control.
- Table rows taller than the density claim allows.

## Build-agent gospel template

The build agent must read `skills/templates/gospel-web_ui.md` before writing UI
code for this medium.

The gospel template is a prompt prepend, not documentation. It is intentionally
strict. It tells the build agent that the locked mockups, manifest tokens, and
iteration log are load-bearing inputs.

The gospel template requires:

- Reading the Visual Specification in full.
- Loading every locked mockup HTML file.
- Using only manifest token values.
- Implementing exact token names as CSS variables or framework equivalents.
- Citing token usage at the top of component files.
- Stopping for a VS amendment when a required token is missing.
- Taking runtime screenshots at phase gates.
- Maintaining SSIM, topology, pHash, and specificity thresholds.
- Rejecting generic SaaS, Bootstrap, default focus rings, greetings, and Quick
  Actions drift.

Any executor that cannot follow the gospel template should not implement
`web_ui` Visual Specifications.

## Token family details

### color

Web UI color tokens are CSS custom properties or design-system constants.

Required semantic keys:

- `surface`
- `surface-elevated`
- `border`
- `text-primary`
- `text-secondary`
- `text-tertiary`
- `accent`
- `accent-hover`
- `accent-pressed`
- `success`
- `warning`
- `danger`
- `focus-ring`

All color tokens must be uppercase six-digit hex values.

The platform color constraint applies: Delta E76 distance between any two color
tokens should be at least 3 unless a Visual Specification explicitly records why
two near-duplicates must remain distinct.

Use `surface` for the default page or app background. Use `surface-elevated` for
panels, cards, sheets, menus, popovers, and other raised regions. Use `border`
for normal separators. Use semantic state tokens for non-decorative status.

Avoid assigning accent colors by hue alone. A saturated blue on a destructive
button is not `accent`; the context decides the semantic token.

### type

Required:

- Family stack, such as `'SF Pro Text', system-ui, sans-serif`.
- Weights used.
- At least five named text styles.
- Each style must include size, weight, leading, and tracking.

Recommended names:

- `display`
- `h1`
- `h2`
- `body`
- `caption`
- `label`
- `metric`
- `code`
- `row`

Use CSS pixel numbers in the token payload. If the mockup uses `rem`, convert to
CSS pixels using the mockup root size.

For dense dashboards, type discipline matters more than type novelty. A 13px
body can work only when line-height, metadata tone, row rhythm, and contrast are
intentional.

### spacing

Required:

- `base` unit.
- `scale` array with at least six values.
- Named gaps in the Visual Specification narrative, even when the schema stores
  only base and scale.

Recommended named gaps:

- `inline-tight`
- `inline`
- `control`
- `section`
- `page`

Default base is 4 CSS pixels for dense web UI, 6 CSS pixels for balanced, and 8
CSS pixels for sparse public surfaces. The extracted token payload should not
pretend a dense dashboard is sparse just because the first revision had loose
spacing.

### radius

Required:

- At least four named values.

Recommended names:

- `sharp`
- `subtle`
- `standard`
- `pillow`
- `full`

The current web UI token schema caps radius values at 64 CSS pixels. Use 64 for
`full` when a design uses fully rounded pills.

Radius is part of trust posture. Enterprise and professional surfaces usually
need sharper values than playful consumer surfaces.

### elevation

Required:

- At least three shadow tokens in the Visual Specification.
- Each shadow should describe x, y, blur, spread, and color.

Recommended names:

- `none`
- `subtle`
- `raised`
- `overlay`

Do not use shadow as the only way to distinguish every card. Dense dashboard UI
usually benefits from separators, tone, and grouping before shadow.

### motion

Required:

- At least three named timings.
- Each timing must include duration in milliseconds and easing.

Recommended names:

- `focus`
- `state_change`
- `expressive`

Curves may be cubic-bezier functions or named CSS easing curves. Motion must
honor reduced-motion expectations even if the locked mockup is static.

For calm or restrained operator UI, focus and state-change durations should stay
short and functional. Avoid bouncy easing unless the declared preset is
playful or expressive.

### density

Required:

- `rows_visible_at_800pt`

Default claims:

- Dense: at least 30 rows visible at 800pt content height when row-based.
- Balanced: at least 15 rows visible at 800pt content height when row-based.
- Sparse: at least 8 rows visible at 800pt content height when row-based.

The number is a claim the reviewer can inspect. If a screen is not row-based,
document the equivalent density proxy, such as number of visible incidents,
widgets, chart regions, workflow steps, or editable fields.

### focus

Required:

- Ring offset.
- Color alpha percentage.
- Radius.

Focus must not be the browser default `outline: 2px solid blue`.

Acceptable focus treatments:

- Tokenized outline color plus offset.
- Tokenized box-shadow ring.
- Tokenized inset ring when layout cannot tolerate outside offset.

Focus treatment must be visible against every surface token used by controls.

## Reference capture rules

For `web_ui`, references are full-page screenshots at 1440 by 900.

Capture references with the agent browser MCP, an equivalent headless browser, or
`scripts/regen_mockup.py` when the reference is local HTML.

Record for each reference:

- Source URL or source file.
- Capture timestamp from the machine-local clock.
- SHA256 of the PNG.
- pHash of the PNG.
- CLIP embedding hash.
- Width and height.
- Role: inspiration, anti-pattern, brand, competitor, historical,
  operator-supplied, or other.
- Note explaining why the reference matters.

Do not use cropped marketing screenshots as dashboard references unless the crop
contains the actual dashboard region being studied. Do not use Dribbble shots as
operator references unless the brief explicitly wants a concept aesthetic and
the anti-pattern risk is documented.

References should include at least one negative example when the adjacent
rejected preset is risky.

## Mockup format details

Mockup files live in `mockups/`.

Required names:

- `scaffold-{N}-{anchor}-rev{M}.html`
- `scaffold-{N}-{anchor}-rev{M}.png`
- `iter-{N}-{anchor}-rev{M}.html`
- `iter-{N}-{anchor}-rev{M}.png`
- `locked-{anchor}.html`
- `locked-{anchor}.png`

Each HTML file is self-contained:

- No external CSS.
- No JavaScript dependency.
- No external image dependency.
- No remote fonts.
- No build step.
- Embedded data URLs are allowed.
- Simple solid backgrounds are allowed.
- The HTML must open directly in a browser.

Each PNG must be captured from the corresponding HTML at a 1440 by 900 viewport.
Do not manually resize PNGs after capture.

The mockup must include enough state to enforce runtime implementation:

- Selected state.
- Hover implication.
- Focus implication.
- Disabled state where controls can be unavailable.
- Loading, empty, or error state when core to the flow.
- Destructive or high-risk action state where relevant.

## Adjudication question set (medium-specific extensions)

Beyond the universal four reviewer questions, web UI adjudication asks:

1. Does the mockup show realistic populated data, not lorem ipsum or fake
   generic records?
2. Is the layout topology consistent with the declared axis: single-pane,
   list-detail, or multi-region?
3. Does the type discipline survive at 1440 by 900 without awkward line breaks,
   orphaned widows in headings, or clipped control text?
4. Are interactive states such as hover, focus, pressed, selected, disabled,
   loading, empty, and destructive implied by the visual treatment?
5. Does the first viewport show the real product, workflow, or object of work
   rather than a marketing wrapper around it?
6. Is the density claim visible, measurable, and consistent with row heights,
   section gaps, and content grouping?
7. Are accents used for meaning rather than decoration?
8. Does the result resist the adjacent rejected preset?
9. Does every visible domain term come from the brief, references, or realistic
   sample data?
10. Can a keyboard user see where focus is without relying on browser defaults?

## Validation history

- v1.0 - 2026-05-10 - initial creation
