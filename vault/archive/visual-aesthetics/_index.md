---
type: aesthetic-index
description: "Preset and medium registry for the Visual Specification System."
version: 1.0
last_updated: 2026-05-10T11:13
presets:
  - name: operator_triage
    axes:
      density: dense
      topology: list-detail
      expressiveness: restrained
      motion: subtle
      platform: web_app
      trust: professional
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: native_ui
        applicability: secondary
  - name: operator_admin
    axes:
      density: dense
      topology: list-detail
      expressiveness: restrained
      motion: functional
      platform: web_app
      trust: enterprise
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: native_ui
        applicability: secondary
  - name: observability_console
    axes:
      density: dense
      topology: multi-region
      expressiveness: restrained
      motion: functional
      platform: web_app
      trust: enterprise
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: data_visualization
        applicability: secondary
  - name: executive_analytics
    axes:
      density: balanced
      topology: multi-region
      expressiveness: restrained
      motion: subtle
      platform: web_app
      trust: enterprise
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: presentation
        applicability: secondary
      - medium: document_typography
        applicability: secondary
      - medium: data_visualization
        applicability: primary
  - name: developer_tools
    axes:
      density: balanced
      topology: list-detail
      expressiveness: restrained
      motion: functional
      platform: web_app
      trust: professional
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: native_ui
        applicability: secondary
  - name: apple_consumer
    axes:
      density: sparse
      topology: single-pane
      expressiveness: expressive
      motion: expressive
      platform: marketing
      trust: approachable
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: native_ui
        applicability: primary
      - medium: presentation
        applicability: secondary
  - name: apple_native
    axes:
      density: sparse
      topology: list-detail
      expressiveness: restrained
      motion: subtle
      platform: native
      trust: approachable
    applies_to_mediums:
      - medium: native_ui
        applicability: primary
  - name: things_calm
    axes:
      density: sparse
      topology: list-detail
      expressiveness: quiet
      motion: subtle
      platform: native
      trust: approachable
    applies_to_mediums:
      - medium: native_ui
        applicability: primary
  - name: vercel_marketing
    axes:
      density: balanced
      topology: single-pane
      expressiveness: expressive
      motion: expressive
      platform: marketing
      trust: professional
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: presentation
        applicability: secondary
      - medium: video_animation
        applicability: secondary
  - name: editorial_premium
    axes:
      density: sparse
      topology: single-pane
      expressiveness: editorial
      motion: subtle
      platform: print
      trust: luxury
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: document_typography
        applicability: primary
  - name: fintech_precise
    axes:
      density: balanced
      topology: list-detail
      expressiveness: restrained
      motion: functional
      platform: web_app
      trust: financial
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: native_ui
        applicability: secondary
  - name: playful_consumer
    axes:
      density: balanced
      topology: single-pane
      expressiveness: playful
      motion: expressive
      platform: web_app
      trust: approachable
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: native_ui
        applicability: primary
      - medium: presentation
        applicability: primary
      - medium: video_animation
        applicability: primary
      - medium: game_ui
        applicability: primary
  - name: data_scientific
    axes:
      density: dense
      topology: multi-region
      expressiveness: restrained
      motion: subtle
      platform: web_app
      trust: professional
    applies_to_mediums:
      - medium: web_ui
        applicability: primary
      - medium: presentation
        applicability: primary
      - medium: document_typography
        applicability: secondary
      - medium: data_visualization
        applicability: primary
mediums:
  - id: web_ui
    applicable_presets: [operator_triage, operator_admin, observability_console, executive_analytics, developer_tools, apple_consumer, vercel_marketing, editorial_premium, fintech_precise, playful_consumer, data_scientific]
  - id: native_ui
    applicable_presets: [operator_triage, operator_admin, developer_tools, apple_consumer, apple_native, things_calm, fintech_precise, playful_consumer]
  - id: presentation
    applicable_presets: [executive_analytics, apple_consumer, vercel_marketing, playful_consumer, data_scientific]
  - id: brand_identity
    applicable_presets: []
  - id: video_animation
    applicable_presets: [vercel_marketing, playful_consumer]
  - id: 3d_render
    applicable_presets: []
  - id: document_typography
    applicable_presets: [executive_analytics, editorial_premium, data_scientific]
  - id: game_ui
    applicable_presets: [playful_consumer]
  - id: data_visualization
    applicable_presets: [observability_console, executive_analytics, data_scientific]
adjacency_map: {}
---

# Aesthetic Preset Registry

## Presets × Mediums matrix

| Preset | web_ui | native_ui | presentation | brand_identity | video | 3d_render | document_typography | game_ui | data_visualization |
|--------|--------|-----------|--------------|----------------|-------|-----------|---------------------|---------|--------------------|
| operator_triage | ✓ | ✓ secondary | — | — | — | — | — | — | — |
| operator_admin | ✓ | ✓ secondary | — | — | — | — | — | — | — |
| observability_console | ✓ | — | — | — | — | — | — | — | ✓ secondary |
| executive_analytics | ✓ | — | ✓ secondary | — | — | — | ✓ secondary | — | ✓ |
| developer_tools | ✓ | ✓ secondary | — | — | — | — | — | — | — |
| apple_consumer | ✓ | ✓ | ✓ secondary | — | — | — | — | — | — |
| apple_native | — | ✓ | — | — | — | — | — | — | — |
| things_calm | — | ✓ | — | — | — | — | — | — | — |
| vercel_marketing | ✓ | — | ✓ secondary | — | ✓ secondary | — | — | — | — |
| editorial_premium | ✓ | — | — | — | — | — | ✓ | — | — |
| fintech_precise | ✓ | ✓ secondary | — | — | — | — | — | — | — |
| playful_consumer | ✓ | ✓ | ✓ | — | ✓ | — | — | ✓ | — |
| data_scientific | ✓ | — | ✓ | — | — | — | ✓ secondary | — | ✓ |

## Per-medium preset suggestions

- web_ui: any of 11 (excludes apple_native, things_calm)
- native_ui: 8 presets that apply
- presentation: 5 presets that apply
- brand_identity: no presets currently; create project-specific brand or use system aesthetic
- video: 3 presets (vercel_marketing, playful_consumer secondary); most projects need custom
- 3d_render: no presets currently; most projects need custom
- document_typography: 4 presets (editorial_premium primary)
- game_ui: 1 preset (playful_consumer); most projects need custom
- data_visualization: 4 presets

## Adjacency map

Preset files populate adjacency relationships. This root registry starts with an empty `adjacency_map` so downstream resolvers can distinguish "no adjacencies declared yet" from "registry missing."

## How presets get added

Not all preset-medium cells are filled. For mediums with sparse preset coverage such as brand_identity, video, 3d_render, and game_ui, projects use custom aesthetics until outcome-backed preset coverage expands. Wave E grows this registry only after shipped projects provide enough references, outcomes, changelog entries, and regression checks to justify a durable default.
