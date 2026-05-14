---
type: axes-medium-extensions
description: "Medium-specific visual axes layered on top of the six universal Visual Specification System axes."
version: 1.0
---

# Medium Extension Axes

## web_ui

No extension axes beyond the universal six. Web UI contracts are fully expressed through density, topology, expressiveness, motion, platform, and trust. Medium plugins may still narrow valid values or add parity checks for responsive behavior, CSS token extraction, focus states, and runtime screenshots.

## native_ui

### Extension axis: platform_native

#### `iOS-idiomatic`

iOS-idiomatic work follows Apple's interaction, navigation, typography, and material conventions closely enough that the result feels native before it feels branded. Dynamic Type, safe areas, SF symbol posture, sheets, tab bars, navigation stacks, and haptic/gesture expectations must be respected. Custom visual personality is allowed only where it does not break system affordances or accessibility behavior.

#### `Android-idiomatic`

Android-idiomatic work follows Material and Android platform conventions for navigation, hierarchy, density, feedback, and system integration. It should respect Android status/navigation bars, touch target expectations, typography scaling, elevation or tonal surface rules, and back behavior. Brand expression should be translated into the platform rather than pasted on as web styling.

#### `desktop-idiomatic`

Desktop-idiomatic work follows macOS, Windows, or Linux desktop expectations for window chrome, menus, sidebars, keyboard access, selection, resizable panes, and pointer precision. It can support denser information than mobile because the user has larger viewports and finer input. The contract must name the target desktop platform when platform conventions differ.

#### `cross-platform-acceptable`

Cross-platform-acceptable work is intentionally shared across multiple OS targets while still preserving basic native affordances. It should avoid controls or navigation patterns that feel actively wrong on any supported platform, even if it does not maximize each platform's idiom. This value is appropriate for Electron, React Native, Flutter, or shared design-system products where consistency is a product requirement.

## presentation

### Extension axis: narrative_arc

#### `chronological`

Chronological decks move through time, sequence, rollout, process, or historical development. Slide order should make temporal position obvious through titles, section labels, timelines, or recurring markers. This value fits project retrospectives, implementation plans, launch sequences, and incident narratives.

#### `thematic`

Thematic decks organize around ideas, arguments, pillars, audiences, or strategic themes rather than time. Each section should have a clear thesis and consistent visual treatment so the viewer understands why slides belong together. This value fits strategy decks, creative briefs, brand narratives, and thought-leadership presentations.

#### `comparative`

Comparative decks place alternatives, segments, competitors, scenarios, or before/after states in direct relationship. Layouts should preserve common scales, repeated positions, and equivalent evidence so comparison is fair. This value fits vendor selections, market scans, design options, pricing analysis, and executive tradeoff reviews.

#### `mixed`

Mixed decks use more than one narrative structure because the subject genuinely requires it. The contract must name where the arc changes, such as chronological setup followed by comparative options. This value should not excuse a deck with no story; it should make transitions between story modes explicit.

## brand_identity

### Extension axis: mark_personality

#### `geometric`

Geometric marks rely on simple constructed shapes, measured proportions, grids, and controlled angles or curves. They tend to read as precise, engineered, scalable, and easy to systematize across applications. The validation focus should include optical balance, small-size survival, and whether the geometry creates a distinctive silhouette.

#### `organic`

Organic marks rely on natural curves, hand-shaped forms, asymmetry, or softer contours. They can communicate warmth, care, craft, movement, or human presence when a strict grid would feel wrong. The contract should still define repeatable rules so the mark does not become mushy or inconsistent across applications.

#### `wordmark-only`

Wordmark-only systems make the name itself the primary identifier without a separate symbol. Typography, spacing, case, ligatures, and letter modifications must carry enough distinctiveness to survive without an icon. Validation should test small sizes, monochrome usage, app-header usage, and whether the wordmark remains legible in real contexts.

#### `symbol-and-wordmark`

Symbol-and-wordmark systems use a standalone symbol plus a typographic name lockup. The symbol must be recognizable alone, and the lockup must have clear spacing, alignment, minimum size, and background rules. Validation should include both combined and separated usage across product, social, document, and environmental applications.

#### `dynamic`

Dynamic identity systems deliberately vary mark, color, layout, or generated form while preserving a recognizable rule. The rule must be explicit enough that future variations are not arbitrary. Validation should test whether multiple generated or applied instances still feel like one brand family.

## video_animation

### Extension axis: pacing_register

#### `calm`

Calm video pacing uses longer holds, gentler transitions, and fewer simultaneous visual events. It gives viewers time to inspect product details, read captions, or absorb an idea without pressure. This value fits trust-building explainers, premium product moments, institutional content, and accessible instructional videos.

#### `dramatic`

Dramatic pacing uses contrast, reveals, timing changes, music hits, camera movement, or visual escalation to create emphasis. It should have purposeful peaks and rests rather than nonstop intensity. This value fits launches, campaign openers, investor moments, and brand films where emotion or anticipation matters.

#### `rapid`

Rapid pacing uses quick cuts, short holds, energetic transitions, and compressed information delivery. It requires stricter typography, frame composition, and audio-visual sync because viewers have less time to decode each frame. This value fits social ads, teasers, hype reels, and game or consumer content where energy is part of the promise.

## 3d_render

### Extension axis: realism

#### `photoreal`

Photoreal renders aim to be believable as camera-captured physical scenes. Materials, lighting, shadows, reflections, scale, and lens behavior must be internally consistent and physically plausible. Validation should include material roughness, contact shadows, highlight behavior, camera focal length, and whether any object breaks scale.

#### `stylized-real`

Stylized-real renders preserve believable lighting and form while allowing simplified materials, heightened color, cleaner geometry, or idealized staging. The result should feel intentionally art-directed rather than technically unfinished. Validation should check that stylization is consistent across objects, not a patchwork of realistic and cartoon treatments.

#### `stylized`

Stylized renders prioritize designed shape language, color, silhouette, and mood over physical realism. Lighting and materials can be simplified or symbolic as long as the system is coherent. Validation should focus on shape consistency, readability, palette discipline, and whether the style supports the project domain.

#### `painterly`

Painterly renders emulate brush, illustration, concept-art, or hand-authored image qualities. They can relax geometric and material precision, but composition, depth, and focal hierarchy still need to hold. Validation should test whether the painterly treatment is visible in final resolution rather than only implied by prompt language.

## document_typography

### Extension axis: format_register

#### `editorial`

Editorial documents emphasize reading rhythm, voice, hierarchy, image placement, and article-like pacing. Typography can be more expressive, but it must preserve long-form comfort and source credibility. This value fits magazines, essays, thought-leadership PDFs, annual letters, and premium narrative reports.

#### `technical`

Technical documents emphasize precision, cross-references, code or formula legibility, table structure, and stable headings. Layouts must support scanning, citation, and repeated lookup rather than only linear reading. This value fits API docs, engineering specs, scientific writeups, standards, and implementation manuals.

#### `report`

Report documents combine executive scanning, evidence, tables, charts, recommendations, and appendices. The visual system must make summary, proof, implication, and source distinct. This value fits consulting reports, board packets, research summaries, operating reviews, and audit deliverables.

#### `book`

Book documents emphasize sustained reading, pagination, chapter rhythm, running heads, footnotes, and durable typographic texture. The system must hold across many pages without novelty fatigue. This value fits long-form manuscripts, manuals, catalogs, and print-like digital books.

## game_ui

### Extension axis: diegetic_axis

#### `in-world`

In-world UI exists as part of the game's fiction, such as a cockpit display, wrist device, sign, map object, or physical console. It should obey the material, lighting, perspective, and limitations of the game world. Validation should test legibility under actual gameplay camera conditions, not only as a clean overlay.

#### `meta`

Meta UI sits outside the fiction and speaks directly to the player, such as menus, inventory, settings, matchmaking, or progression screens. It can borrow theme from the world but should prioritize clarity, input predictability, and platform conventions. Validation should include controller, keyboard/mouse, and touch states where applicable.

#### `abstract-overlay`

Abstract-overlay UI is not fully in-world or fully menu-like; it floats over gameplay as symbolic status, targeting, cooldown, damage, or guidance information. It must stay readable against changing backgrounds and movement. Validation should test contrast, scale, animation, and attention cost during representative gameplay scenes.

## data_visualization

### Extension axis: narrative_chart

#### `exploratory`

Exploratory charts let the user inspect, filter, compare, or discover patterns with limited pre-authored conclusion. They need strong axes, legends, interaction states, and visible data provenance because the viewer is doing analytical work. This value fits dashboards, notebooks, research tools, and self-serve analytics.

#### `declarative`

Declarative charts make a specific point and reduce optional interpretation. Title, annotation, encoding, and layout should guide the viewer to the intended conclusion quickly. This value fits executive slides, reports, investor materials, and narrative dashboards where the author owns the claim.

#### `annotated-explainer`

Annotated-explainer charts teach the viewer how to read a pattern, anomaly, process, or causal story. They combine chart structure with labels, callouts, sequencing, highlights, and sometimes progressive disclosure. This value fits public data stories, complex stakeholder education, and analytical content where misunderstanding is likely.
