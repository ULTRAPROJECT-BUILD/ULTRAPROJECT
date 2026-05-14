---
type: skill
name: build-brand-system
description: Create a versioned brand-system file from operator-provided brand assets. Captures brand color palette, typography, application rules, voice/tone, references, anti-patterns, and computes brand-specific CLIP centroid. Brand-system files are project-agnostic but client-scoped; reused across multiple projects.
inputs:
  - brand_slug (required)
  - client_organization_id (required)
  - operator_provided_brand_assets (required: paths to logo files, color guides, typography specs, application examples)
  - operator_provided_brand_voice (optional)
---

# Build Brand System Skill

## Mission

Create a locked, reusable brand-system file from operator-provided brand assets.

This skill runs when a project has a real brand and the Visual Specification
mode is `brand_system`. The brand-system file is project-agnostic but
client-scoped. It lives in `vault/archive/brand-systems/{brand_slug}.md` and can
govern multiple future projects for the same brand.

Default behavior is autonomous:

- Use only assets the operator provided or assets already stored in the client
  vault.
- Extract the strongest available palette, type, application, voice, reference,
  and anti-pattern evidence.
- Compute a brand-specific CLIP centroid from approved brand references when
  image dependencies are installed.
- If CLIP dependencies are unavailable, write the brand-system file with a
  declared centroid path and record the centroid as pending in validation
  history; do not block creation when the source brand evidence is otherwise
  sufficient.
- Validate the frontmatter against `schemas/brand-system.schema.json`.
- Do not ask the operator for confirmation during the default build. Any
  missing material is recorded as a follow-up in the validation history.

The output is not a mood board. It is a reusable contract for Visual
Specification: colors, typography, application rules, voice and tone, approved
references, anti-patterns, and the centroid path that `mode=brand_system` uses
for visual gate checks.

## Inputs

Required:

- `brand_slug`: stable lowercase slug matching `^[a-z0-9][a-z0-9_-]*$`.
- `client_organization_id`: organization that owns or supplied the brand.
- `operator_provided_brand_assets`: one or more repository-relative paths to
  logos, color guides, typography specs, brand guide PDFs, screenshots,
  application examples, campaign examples, packaging, signage, or product UI.

Optional:

- `operator_provided_brand_voice`: text file, markdown notes, or prompt text
  describing voice and tone.

Use the local clock before writing:

```bash
date +%Y-%m-%d
date +"%Y-%m-%dT%H:%M"
```

## Working Paths

Brand-system file:

```text
vault/archive/brand-systems/{brand_slug}.md
```

Reference directory:

```text
vault/archive/brand-systems/references/{brand_slug}/
```

Recommended subdirectories:

```text
vault/archive/brand-systems/references/{brand_slug}/source-assets/
vault/archive/brand-systems/references/{brand_slug}/application-studies/
vault/archive/brand-systems/references/{brand_slug}/anti-patterns/
vault/archive/brand-systems/references/{brand_slug}/derived/
```

CLIP centroid:

```text
vault/archive/visual-aesthetics/centroids/{brand_slug}.npy
```

Schema:

```text
schemas/brand-system.schema.json
```

Template:

```text
vault/archive/brand-systems/_template.md
```

## Step 1 — Parse brand assets

Normalize all provided paths before reading:

- Reject paths that are outside the repository or outside allowed client vault
  roots.
- Keep originals in place; do not move operator assets unless the task
  explicitly asks for reorganization.
- Copy or reference derived working files under
  `vault/archive/brand-systems/references/{brand_slug}/`.
- Preserve source filenames in the references section.

Classify each asset:

- `logo_primary`
- `logo_secondary`
- `wordmark`
- `symbol`
- `brand_guide_pdf`
- `color_spec`
- `typography_spec`
- `voice_spec`
- `product_ui`
- `marketing_page`
- `email`
- `social`
- `packaging`
- `signage`
- `photo_overlay`
- `presentation`
- `unknown`

Asset-specific extraction:

- Markdown, text, JSON, YAML, CSS, SVG, and HTML can be read directly.
- PDF brand guides may need text extraction. Use available local tooling first
  (`pdftotext`, `python` libraries already present, or manual summary from the
  visible text). Record extraction limitations.
- Raster logos and screenshots can be sampled for color, layout, and reference
  evidence.
- SVG logos should be parsed for fill/stroke colors and viewBox geometry.
- Existing design-token files should be treated as higher authority than
  inferred image sampling.

Write an internal extraction note in the brand-system body:

- source asset
- type
- evidence extracted
- confidence
- limitations

If assets conflict, precedence is:

1. Current official brand guide or design-token file.
2. Current production product/application examples.
3. Current marketing site or campaign material.
4. Legacy PDFs, screenshots, and one-off campaign images.
5. Inferred values from logos.

## Step 2 — Extract color palette

Build semantic color tokens for frontmatter. The schema requires at least five
tokens, each a hex color.

Minimum frontmatter palette:

- `primary`
- `secondary`
- `accent`
- `surface`
- `ink`

Recommended additional tokens:

- `background`
- `surface_alt`
- `muted`
- `border`
- `success`
- `warning`
- `danger`
- `focus`
- `logo_primary`
- `logo_reversed`

Extraction methods:

- From design-token JSON/YAML/CSS: preserve semantic names where possible.
- From brand guide PDFs: transcribe official hex values exactly.
- From SVG logo files: parse `fill`, `stroke`, and CSS variables.
- From raster logos or screenshots: sample dominant colors, then normalize to
  the nearest official value if an official guide exists.
- From application examples: identify supporting neutrals, state colors, and
  contrast pairings.

Rules:

- Do not invent a one-note palette from the logo alone. Include neutral surface
  and text colors that make the brand usable in product UI.
- Do not create tints as authoritative tokens unless the brand guide names them
  or they are visibly repeated across official applications.
- Record contrast-sensitive combinations in the body.
- Record forbidden combinations when evidence shows the brand never uses them.

Validation:

- Every frontmatter color must match `^#[0-9A-Fa-f]{6}$`.
- Use uppercase or lowercase consistently. Prefer uppercase hex.
- Avoid alpha values in frontmatter. Put opacity guidance in the body.

## Step 3 — Extract typography

Build the frontmatter `typography` object:

```yaml
typography:
  display_family: "..."
  body_family: "..."
  fallback_stack: ["Inter", "Helvetica Neue", "Arial", "sans-serif"]
  scale:
    display: 48
    headline: 32
    title: 24
    body: 16
    caption: 12
```

Extraction sources:

- Brand guide typography page.
- Design-token file.
- CSS from official pages.
- Figma or design export JSON if provided.
- Specimen images when no text source exists.

Record:

- Display family.
- Body family.
- Monospace or numeric family if the brand uses one.
- Fallback stack.
- Size scale.
- Line-height rules.
- Weight rules.
- Tracking rules.
- Case rules.
- Medium-specific substitutions.

If the official font is not available locally:

- Preserve the official family name in frontmatter.
- Add installation/substitution notes in the body.
- Choose fallback stack based on shape, not convenience.

Do not choose novelty typefaces for missing fonts. When evidence is incomplete,
prefer a sober fallback and mark confidence as provisional.

## Step 4 — Capture application studies

Capture at least five distinct application contexts. These are what make the
brand-system useful beyond a palette.

Required contexts when source assets allow:

1. Logo on white or light surface.
2. Logo on dark or reversed surface.
3. Logo over photography or rich image.
4. Product UI, document, or operational interface.
5. Marketing, signage, packaging, slide, email, or social application.

For each application study, document:

- study name
- source asset path
- context
- background treatment
- logo lockup used
- color proportions
- typography behavior
- spacing or clear-space observation
- what the study proves
- what not to overgeneralize

Store referenced screenshots or copied source assets under:

```text
vault/archive/brand-systems/references/{brand_slug}/application-studies/
```

When fewer than five application studies are provided:

- Create the brand-system file anyway if the core brand assets are sufficient.
- Mark missing contexts in validation history.
- Add explicit follow-up requests.
- Do not pretend inferred contexts are approved.

## Step 5 — Compute brand-specific CLIP centroid

Use approved brand reference images, not anti-patterns, to compute the centroid.

Preferred references:

- application studies
- product UI screenshots
- current marketing surfaces
- approved logo lockups in real contexts
- approved campaign images

Avoid:

- isolated transparent logos only
- anti-patterns
- low-resolution thumbnails
- outdated campaigns
- screenshots dominated by browser chrome

Command:

```bash
python3 scripts/compute_clip_centroid.py \
  --preset-name "{brand_slug}" \
  --references {approved_reference_pngs...} \
  --out "vault/archive/visual-aesthetics/centroids/{brand_slug}.npy" \
  --json-out "vault/archive/brand-systems/references/{brand_slug}/derived/clip-centroid.json"
```

If the command exits `2`, dependencies are missing. Record the install
instructions from stderr in validation history and keep:

```yaml
clip_centroid_path: vault/archive/visual-aesthetics/centroids/{brand_slug}.npy
```

Do not fabricate a `.npy` file. The path is the intended stable location. The
gate will fail closed if a project tries to use `mode=brand_system` before the
centroid exists and the gate requires it.

If no valid raster references exist:

- Record `centroid_status: pending_reference_images` in validation history.
- Keep the brand-system file schema-valid.
- Require reference capture before the brand system is used to lock a VS.

## Step 6 — Document anti-patterns

Anti-patterns are treatments the build agent must not accidentally produce when
trying to "make it branded."

Document at least five whenever evidence allows:

- wrong logo color or tint
- distorted logo
- logo without clear space
- off-brand color proportions
- typeface substitution that changes personality
- generic stock-photo treatment
- decorative gradients not present in the brand
- over-rounded UI if the brand is precise
- heavy shadows if the brand is flat
- playful copy if the brand voice is direct
- dense enterprise chrome if the brand is consumer-light

For each anti-pattern:

- name it
- describe the failure
- name the evidence source
- explain the corrective rule

Anti-pattern files, if any, go under:

```text
vault/archive/brand-systems/references/{brand_slug}/anti-patterns/
```

Do not use competitor assets as brand anti-patterns unless the operator supplied
them for that purpose. When competitor comparison is useful, describe the visual
move without copying protected material.

## Step 7 — Write brand-system file

Write:

```text
vault/archive/brand-systems/{brand_slug}.md
```

Frontmatter must match `schemas/brand-system.schema.json` exactly. Do not add
extra frontmatter fields.

Required frontmatter:

```yaml
---
type: brand-system
brand_slug: "{brand_slug}"
version: "1.0.0"
client_organization_id: "{client_organization_id}"
color_palette:
  primary: "#000000"
  secondary: "#111111"
  accent: "#222222"
  surface: "#FFFFFF"
  ink: "#111827"
typography:
  display_family: "..."
  body_family: "..."
  fallback_stack: ["Inter", "Helvetica Neue", "Arial", "sans-serif"]
  scale:
    display: 48
    headline: 32
    title: 24
    body: 16
    caption: 12
application_rules:
  logo_usage:
    - "..."
  color_usage:
    - "..."
  typography_usage:
    - "..."
  medium_overrides: {}
voice_tone_guidelines:
  - "..."
references_dir: vault/archive/brand-systems/references/{brand_slug}
anti_patterns:
  - "..."
clip_centroid_path: vault/archive/visual-aesthetics/centroids/{brand_slug}.npy
---
```

Required body sections:

- `# {Brand Name} Brand System`
- `## Constraint Translation Table`
- `## Brand Summary`
- `## Source Assets`
- `## Color Palette`
- `## Typography`
- `## Application Rules`
- `## Application Studies`
- `## Voice & Tone`
- `## References`
- `## Anti-patterns`
- `## CLIP Centroid`
- `## Validation History`

### Constraint Translation Table (required when inheriting brief constraints)

For every brief constraint that names a thing to avoid, fill this table:

| Brief constraint | What's banned | What's still allowed | Operational rule |
|---|---|---|---|
| (verbatim quote from brief) | (the specific forbidden thing) | (everything not in the ban) | (one concrete rule for the brand-system that preserves the allowed) |

Do NOT translate brief constraints into load-bearing positive design principles without running them through this table first.

Recommended body details:

- confidence per extracted decision
- official vs inferred distinction
- contrast pairings
- medium overrides for web UI, native UI, presentation, brand identity, or
  document typography
- update rules for future versions
- unresolved evidence gaps

Versioning:

- New file starts at `1.0.0`.
- Minor updates that add evidence without changing rules become `1.1.0`.
- Patch updates for typo or reference-path fixes become `1.0.1`.
- Breaking changes to palette, type, logo rules, or voice become `2.0.0`.

If a file already exists:

- Do not overwrite blindly.
- Read it, preserve validation history, and create a new version in place only
  when the new evidence is stronger.
- If there is conflicting brand evidence, write a `## Pending Conflict` section
  and keep the old rules unless the newer official asset is clearly
  authoritative.

## Step 8 — Validate against schemas/brand-system.schema.json

Run:

```bash
python3 scripts/validate_schema.py \
  --artifact "vault/archive/brand-systems/{brand_slug}.md" \
  --schema schemas/brand-system.schema.json \
  --artifact-type yaml-frontmatter \
  --json-out "vault/archive/brand-systems/references/{brand_slug}/derived/schema-validation.json"
```

Pass condition:

- JSON result has `"valid": true`.

If validation fails:

- Fix frontmatter, not the schema.
- Do not loosen `schemas/brand-system.schema.json` for a single brand.
- Re-run validation until it passes.

After validation, update `vault/archive/brand-systems/_index.md` with a row for
the brand if the index format already contains a table. If the index has only
placeholder prose, append a short list item:

```markdown
- `{brand_slug}` — `{client_organization_id}`, v1.0.0,
  `vault/archive/brand-systems/{brand_slug}.md`
```

Use `apply_patch` for edits.

## Quality Bar

A usable brand system must answer:

- What colors are authoritative?
- What type families and scale are authoritative?
- How can the logo be used?
- What application contexts prove the brand rules?
- What copy voice should visible language use?
- What visual moves are forbidden?
- Where are the references?
- Where is the CLIP centroid or why is it pending?
- Did the frontmatter schema validate?

If the source assets are weak, the file should say so. A schema-valid but
honest provisional brand system is better than a polished fiction.

## Outputs

Always:

- `vault/archive/brand-systems/{brand_slug}.md`
- `vault/archive/brand-systems/references/{brand_slug}/derived/schema-validation.json`

When source assets are copied or derived:

- `vault/archive/brand-systems/references/{brand_slug}/source-assets/*`
- `vault/archive/brand-systems/references/{brand_slug}/application-studies/*`
- `vault/archive/brand-systems/references/{brand_slug}/anti-patterns/*`
- `vault/archive/brand-systems/references/{brand_slug}/derived/extraction-notes.md`

When CLIP dependencies and references are available:

- `vault/archive/visual-aesthetics/centroids/{brand_slug}.npy`
- `vault/archive/brand-systems/references/{brand_slug}/derived/clip-centroid.json`

Optional:

- Updated `vault/archive/brand-systems/_index.md`

## Completion Criteria

The skill is complete when:

- The brand-system markdown exists at the canonical path.
- Frontmatter validates against `schemas/brand-system.schema.json`.
- The body includes source assets, palette, typography, application rules,
  application studies, voice/tone, references, anti-patterns, centroid status,
  and validation history.
- At least five application contexts are documented, or missing contexts are
  explicitly listed as follow-up evidence.
- The brand can be selected by `visual_quality_target_mode: brand_system`
  without the build agent needing to reinterpret raw brand assets.
