---
type: registry
title: "Platform Client Registry Template"
description: "Registry notes for platform-level operators. Documents Visual Specification System v6 directories and task types introduced by the implementation."
updated: 2026-05-10
---

# Platform Registry Template

This file documents platform-level registry expectations for clean installs.
Copy or merge these notes into the live client registry when bootstrapping a new
OneShot vault.

## v6 Visual Specification Directories

Visual Specification System v6 introduces shared platform directories that live
outside any single client workspace:

| Path | Purpose |
|------|---------|
| `vault/archive/visual-aesthetics/` | Aesthetic axes, presets, medium plugins, centroids, proposals, and closed-loop telemetry artifacts. |
| `vault/archive/visual-aesthetics/presets/` | Versioned aesthetic presets used by `visual_quality_target_mode: preset`. |
| `vault/archive/visual-aesthetics/mediums/` | Medium plugins for `web_ui`, `native_ui`, `presentation`, `brand_identity`, `video_animation`, `3d_render`, `document_typography`, `game_ui`, and `data_visualization`. |
| `vault/archive/visual-aesthetics/proposals/` | Outcome-driven preset update proposals awaiting operator review. |
| `vault/archive/visual-aesthetics/proposals/_promising-but-insufficient/` | Low-data positive telemetry signals that are not eligible for automatic preset updates. |
| `vault/archive/visual-aesthetics/centroids/` | CLIP centroid files for presets, custom aesthetics, and brand systems. |
| `vault/archive/brand-systems/` | Reusable client-scoped brand-system files for `visual_quality_target_mode: brand_system`. |
| `vault/locks/` | Visual-spec logical locks, resolver generation records, and lock backend state. |
| `vault/cache/visual-spec/` | Gate caches for pHash, CLIP, render, schema, LLM scoring, and regression replay. |
| `schemas/` | JSON Schemas for VS frontmatter, manifests, presets, medium plugins, outcomes, waivers, locks, proposals, token payloads, and related artifacts. |

Client-scoped project data remains under:

```text
vault/clients/{client_slug}/
```

Project snapshots may also include visual-spec outcome records used by
closed-loop telemetry:

```text
vault/clients/{client_slug}/snapshots/**/visual-spec-outcome-*.json
vault/snapshots/*/visual-spec-outcome-*.json
```

## v6 Task Types

Visual Specification v6 adds task types that the orchestrator and executor must
treat as first-class:

| Task Type | Purpose | Default Blocking Behavior |
|-----------|---------|---------------------------|
| `visual_spec` | Runs the Visual Specification skill to lock the medium-specific visual contract before build tickets spawn. | Blocks dependent build, self-review, quality-check, and artifact-polish tickets until `check_visual_spec_gate.py --profile vs_full` passes. |
| `visual_spec_review` | Runs independent visual adjudication, adversarial pass, runtime parity review, or operator-review-required telemetry checks. | Blocks only the specific VS revision, waiver, or proposal it reviews. |

Related existing task types still apply:

- `creative_brief`
- `project_plan`
- `build`
- `self_review`
- `quality_check`
- `artifact_polish_review`
- `post_delivery_review`

## Registry Notes For Operators

When a new client is installed:

- Keep client records in `vault/clients/_registry.md`.
- Keep platform Visual Specification assets in the shared archive paths above.
- Do not copy presets or medium plugins into each client workspace unless a
  client-specific fork is intentional and documented.
- Store reusable brand systems in `vault/archive/brand-systems/`, scoped by
  `client_organization_id` in frontmatter.
- Store project-specific custom aesthetics in
  `vault/archive/visual-aesthetics/custom/`.
- Keep lock and cache directories out of client deliverables.

When restoring a vault:

- Restore `vault/archive/visual-aesthetics/`.
- Restore `vault/archive/brand-systems/`.
- Restore `schemas/`.
- Restore `vault/config/platform.md`.
- Restore `vault/config/lock-backend.json` only if the filesystem environment is
  unchanged; otherwise rerun `scripts/probe_lock_backend.py`.
- Rebuild `vault/cache/visual-spec/` if missing. Cache contents are
  performance aids, not authority.

## See Also

- `skills/visual-spec.md`
- `skills/consolidate-aesthetics.md`
- `skills/build-brand-system.md`
- `schemas/visual-spec-frontmatter.schema.json`
- `schemas/brand-system.schema.json`
- `vault/archive/visual-aesthetics/_index.md`
- `vault/archive/brand-systems/_index.md`
