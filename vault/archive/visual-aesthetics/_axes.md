---
type: axes-value-table
description: "Universal visual axis-value definitions used when resolving or reviewing Visual Specification System aesthetics."
version: 1.0
axes:
  density:
    meaning: "Controls how much useful information appears in a standard viewport or frame without changing the underlying task scope."
    values:
      - value: sparse
        meaning: "Low information per viewport, generous whitespace, and one primary decision or reading unit at a time."
        medium_notes:
          web_ui: "Hero, settings, or consumer flows with few simultaneous records."
          presentation: "One idea per slide."
          3d_render: "One dominant subject with uncomplicated surroundings."
      - value: balanced
        meaning: "Moderate information per viewport, enough grouping for scan speed without forcing high-density operator work."
        medium_notes:
          web_ui: "Forms, dashboards, and content surfaces with two to four visible groups."
          presentation: "Two major ideas or a chart plus interpretation."
          document_typography: "Comfortable report density with headings, tables, and prose sharing the page."
      - value: dense
        meaning: "High information per viewport, optimized for scanning, triage, comparison, and repeated expert use."
        medium_notes:
          web_ui: "At least 30 rows visible at 800pt content height when row-based."
          presentation: "Up to three tightly related information units per slide."
          3d_render: "At least three named subjects or material/lighting relationships in the scene."
    default_token_postures:
      sparse: "spacing.base 8pt; scale [8, 16, 24, 32, 48, 64, 96]; body 16pt; section gaps 48-96pt."
      balanced: "spacing.base 6pt; scale [6, 12, 16, 24, 32, 48, 64]; body 14-16pt; section gaps 24-48pt."
      dense: "spacing.base 4pt; scale [4, 8, 12, 16, 20, 24, 32]; body 13pt; section gaps <=16pt."
    default_anti_patterns:
      - "Claiming dense while rows exceed 56pt or only a few records fit in the viewport."
      - "Claiming sparse while the surface still shows competing tables, charts, and panels."
      - "Using whitespace as decoration when the target user needs comparison speed."
    pairs_naturally_with:
      - "sparse with topology: single-pane"
      - "balanced with topology: list-detail"
      - "dense with topology: list-detail or multi-region"
    conflicts_with:
      - "dense with expressiveness: expressive unless color and motion are tightly disciplined"
      - "sparse with operator triage workflows"
      - "balanced when the brief demands either premium editorial restraint or high-throughput operations"
  topology:
    meaning: "Controls the structural arrangement of information, actions, and regions in a viewport, slide, page, frame, or composition."
    values:
      - value: single-pane
        meaning: "One dominant visual or task region, with secondary actions subordinated to the main read."
        medium_notes:
          web_ui: "Landing pages, focused editors, checkout steps, or single-object detail views."
          presentation: "One stage with a title, visual, and supporting note."
          brand_identity: "One mark, lockup, or application study controls the composition."
      - value: list-detail
        meaning: "A repeated collection and a selected item or work area are visible together."
        medium_notes:
          web_ui: "Inbox, issue tracker, CRM, file browser, or review queue."
          native_ui: "Sidebar plus content detail on desktop or hierarchical drill-in on mobile."
          presentation: "Overview-to-detail sequence where one selected item is explained."
      - value: multi-region
        meaning: "Several coordinated regions are visible at once, each with a distinct analytical or operational role."
        medium_notes:
          web_ui: "Observability, analytics, command center, or comparison dashboard."
          data_visualization: "Small multiples, linked charts, and annotation regions."
          document_typography: "Page layouts with prose, chart, table, and callout zones."
    default_token_postures:
      single-pane: "max content width 680-960px; one primary grid column; secondary actions inline or trailing."
      list-detail: "primary pane ratio 1.5:1 or greater; list row height 28-44pt; persistent selection affordance."
      multi-region: "12-column or named-region grid; region gutters 16-24pt; charts and controls aligned to shared baselines."
    default_anti_patterns:
      - "Equal-weight panes that make no region clearly primary."
      - "Card grids used as a substitute for real workflow topology."
      - "Multi-region layouts whose regions do not share filters, time ranges, or state."
    pairs_naturally_with:
      - "single-pane with density: sparse"
      - "list-detail with density: balanced or dense"
      - "multi-region with trust: enterprise or professional"
    conflicts_with:
      - "single-pane with dense operator workloads"
      - "multi-region with consumer onboarding unless the brief explicitly demands comparison"
      - "list-detail with brand identity marks unless expressed as application-suite structure"
  expressiveness:
    meaning: "Controls how strongly color, imagery, typography, shape, and composition signal personality beyond pure utility."
    values:
      - value: restrained
        meaning: "Visual personality is quiet and subordinate to task clarity, hierarchy, and trust."
        medium_notes:
          web_ui: "Neutral surfaces, limited accent use, precise borders, and low decorative load."
          presentation: "Business or analytical slides where charts and evidence lead."
          data_visualization: "Color encodes meaning before brand personality."
      - value: balanced
        meaning: "Personality is visible but contained, usually through selective brand color, type contrast, or composition rhythm."
        medium_notes:
          web_ui: "Product surfaces that need memorability without slowing repeated use."
          document_typography: "Reports that need editorial confidence and clear scanning."
          brand_identity: "Systems with enough distinction to own applications while staying versatile."
      - value: expressive
        meaning: "Visual personality is a first-order goal, with bolder color, type, imagery, or motion carrying the experience."
        medium_notes:
          web_ui: "Marketing, consumer, launch, or playful product surfaces."
          video_animation: "Motion and framing visibly shape emotional register."
          game_ui: "The interface can carry theme, fantasy, reward, or character."
    default_token_postures:
      restrained: "1 accent hue; neutral surfaces; radius 4-8px; type contrast ratio 1.125-1.2; decorative assets optional."
      balanced: "2-3 brand hues; controlled illustration or imagery; radius 6-12px; display/body contrast clear but not theatrical."
      expressive: "3+ intentional color roles; display type may lead; image or motion assets required for public surfaces."
    default_anti_patterns:
      - "Restrained surfaces that become anonymous because hierarchy and material detail are missing."
      - "Balanced surfaces with ungoverned accent sprawl."
      - "Expressive surfaces that use novelty without supporting the domain or workflow."
    pairs_naturally_with:
      - "restrained with density: dense"
      - "balanced with trust: professional"
      - "expressive with platform: marketing or trust: consumer"
    conflicts_with:
      - "expressive with safety-critical enterprise workflows unless separately justified"
      - "restrained with a brief asking for visibly distinctive public brand work"
      - "balanced when no clear brand or domain signal exists"
  motion:
    meaning: "Controls how much temporal behavior is part of the aesthetic contract, including transitions, feedback, choreography, and video pacing."
    values:
      - value: calm
        meaning: "Motion is minimal, slow enough to preserve attention, and mostly used for orientation or continuity."
        medium_notes:
          web_ui: "150-220ms transitions, opacity or small transforms, no looping decorative motion."
          presentation: "Cuts or gentle fades; builds only when they improve comprehension."
          video_animation: "Longer holds and measured transitions."
      - value: standard
        meaning: "Motion supports state change, feedback, and user confidence without becoming the main visual event."
        medium_notes:
          web_ui: "100-180ms control feedback and functional page transitions."
          native_ui: "Platform-standard navigation, sheet, menu, and focus behavior."
          data_visualization: "Transitions clarify changed filters or time ranges."
      - value: expressive
        meaning: "Motion is visibly authored and contributes to brand, delight, narrative, or dramatic emphasis."
        medium_notes:
          web_ui: "Launch moments, product reveals, and playful feedback can use choreography."
          video_animation: "Timing, easing, camera movement, and transitions define the piece."
          game_ui: "Rewards, damage, cooldowns, and menu state may animate distinctly."
    default_token_postures:
      calm: "duration.short 120ms; duration.base 180ms; duration.long 260ms; easing standard ease-out."
      standard: "duration.short 90ms; duration.base 150ms; duration.long 220ms; easing chosen by state change."
      expressive: "duration.short 120ms; duration.base 240ms; duration.long 480ms; custom easing allowed with reduced-motion fallback."
    default_anti_patterns:
      - "Looping or ambient motion in high-focus operator surfaces."
      - "Expressive animation without reduced-motion treatment."
      - "State changes with no feedback on native or game UI controls."
    pairs_naturally_with:
      - "calm with expressiveness: restrained"
      - "standard with topology: list-detail"
      - "expressive with expressiveness: expressive"
    conflicts_with:
      - "expressive with density: dense unless limited to rare events"
      - "calm with video work that requires dramatic pacing"
      - "standard if the platform has stricter native motion conventions"
  platform:
    meaning: "Controls which medium conventions, input assumptions, and environmental expectations the visual system should honor."
    values:
      - value: web-app
        meaning: "Designed for browser-delivered product surfaces with responsive layout, DOM/CSS tokens, and mixed pointer/keyboard interaction."
        medium_notes:
          web_ui: "Primary idiom for dashboards, SaaS apps, landing pages, and browser tools."
          data_visualization: "Charts may be interactive and responsive."
          presentation: "Only applicable when slides are built in web-native frameworks."
      - value: native
        meaning: "Designed around OS idioms, system typography, platform navigation, safe areas, and accessibility conventions."
        medium_notes:
          native_ui: "Uses iOS, Android, macOS, Windows, or cross-platform conventions intentionally."
          game_ui: "Native only when shell or platform menus need OS behavior."
          web_ui: "Avoid unless the target is a desktop-web app deliberately mimicking native interaction."
      - value: marketing
        meaning: "Designed for persuasion, first-impression clarity, brand recall, and public storytelling rather than repeated operator throughput."
        medium_notes:
          web_ui: "Landing, launch, product, pricing, and branded public pages."
          video_animation: "Motion graphics and campaign pieces."
          brand_identity: "Application studies that emphasize recognition over task completion."
    default_token_postures:
      web-app: "responsive breakpoints; CSS token families; focus rings; keyboard states; density and component tokens explicit."
      native: "system type ramps; platform spacing; safe-area rules; native control affordances; accessibility size classes."
      marketing: "viewport-led sections; display type; image or motion assets; generous first-read hierarchy."
    default_anti_patterns:
      - "Web controls that pretend to be native without honoring platform behavior."
      - "Marketing composition used for repeated administrative workflows."
      - "Native UI that ignores dynamic type, safe areas, or expected navigation patterns."
    pairs_naturally_with:
      - "web-app with density: balanced or dense"
      - "native with motion: calm or standard"
      - "marketing with expressiveness: balanced or expressive"
    conflicts_with:
      - "marketing with trust: enterprise operator consoles"
      - "native with web-only token extraction unless a native plugin is active"
      - "web-app with brand identity deliverables that need lockup/application rules first"
  trust:
    meaning: "Controls how risk, authority, accessibility, and institutional confidence should temper visual decisions."
    values:
      - value: consumer
        meaning: "Trust is built through approachability, clarity, responsiveness, and emotional fit for a broad audience."
        medium_notes:
          web_ui: "Clear labels, friendly hierarchy, strong onboarding, and forgiving empty states."
          native_ui: "Platform familiarity and accessibility are more important than novelty."
          game_ui: "Trust includes legibility and consistent feedback under play pressure."
      - value: professional
        meaning: "Trust is built through competence, precision, consistent hierarchy, and useful density for trained users."
        medium_notes:
          web_ui: "Work surfaces, developer tools, analytics, and internal products."
          presentation: "Executive or stakeholder evidence must read as controlled and defensible."
          document_typography: "Report layouts need source clarity, table discipline, and stable navigation."
      - value: enterprise
        meaning: "Trust is built through risk control, auditability, restrained styling, accessibility, and unambiguous state."
        medium_notes:
          web_ui: "Admin, finance, security, compliance, and operational command surfaces."
          data_visualization: "Charts must make uncertainty, source, and filters inspectable."
          brand_identity: "Applications must avoid ambiguity in official or regulated contexts."
    default_token_postures:
      consumer: "AA contrast minimum; friendly radius 8-16px; clear empty/loading/error states; accent can carry warmth."
      professional: "AA contrast; radius 4-10px; restrained accents; visible metadata; consistent table and chart treatments."
      enterprise: "AA required and AAA for critical body text when feasible; radius 2-8px; explicit status tokens; destructive actions nested."
    default_anti_patterns:
      - "Consumer polish that hides state, source, or consequence."
      - "Professional surfaces with marketing-style hero scale in task areas."
      - "Enterprise surfaces where color alone communicates risk or permission."
    pairs_naturally_with:
      - "consumer with expressiveness: balanced or expressive"
      - "professional with density: balanced"
      - "enterprise with expressiveness: restrained and topology: multi-region"
    conflicts_with:
      - "enterprise with unqualified playful motion or decorative color"
      - "consumer with overloaded dense operator layouts"
      - "professional with vague copy, weak hierarchy, or generic card grids"
---

# Universal Visual Axis Value Definitions

## Density

### density: sparse

**Means at runtime:**
- One primary decision, message, object, or visual subject is dominant in the viewport or frame.
- Web and native screens should usually show fewer than 12 repeated records at 800pt content height, or no repeated records at all.
- Presentation slides carry one idea, one chart, or one hero statement; document pages use generous margins and long reading rhythm.

**Default token postures:**
- `spacing.base = 8pt`
- `spacing.scale = [8, 16, 24, 32, 48, 64, 96]`
- `type.body.size = 16pt`
- `type.body.leading = 1.55x`
- `section.gap = 48-96pt`

**Default anti-patterns:**
- Empty decorative whitespace that hides required state, controls, or evidence.
- Sparse dashboards that force scrolling just to compare ordinary records.
- Oversized cards that make a task surface feel like a landing page.

**Pairs naturally with:**
- `topology: single-pane`
- `expressiveness: balanced` or `expressiveness: expressive`
- `motion: calm`
- `trust: consumer`

**Conflicts with:**
- `topology: multi-region` when all regions are operationally required.
- `trust: enterprise` if sparse layout hides audit-critical metadata.
- High-throughput triage, monitoring, queue review, and bulk-edit workflows.

### density: balanced

**Means at runtime:**
- The viewport shows enough context to compare and decide, but still gives each region room to breathe.
- Web and native screens typically show 12-24 repeated rows, two to four content groups, or one chart plus supporting controls.
- Slides can hold two related ideas, or one chart with title, interpretation, and source.

**Default token postures:**
- `spacing.base = 6pt`
- `spacing.scale = [6, 12, 16, 24, 32, 48, 64]`
- `type.body.size = 14-16pt`
- `type.body.leading = 1.45-1.55x`
- `section.gap = 24-48pt`

**Default anti-patterns:**
- Splitting every object into equal cards when a table or list would scan faster.
- Reducing type below 14pt without also tightening row structure and hierarchy.
- Adding decorative blank bands between functional regions.

**Pairs naturally with:**
- `topology: list-detail`
- `expressiveness: restrained` or `expressiveness: balanced`
- `motion: standard`
- `trust: professional`

**Conflicts with:**
- `platform: marketing` when the first viewport must land a simple brand or product claim.
- `density: dense` requirements such as 30+ visible rows.
- `density: sparse` premium editorial or hero-led treatments.

### density: dense

**Means at runtime:**
- Row heights are <=32pt and content rows are >=30 visible at 800pt content height for row-based UIs.
- Section gaps are <=16pt, and repeated values align to a stable grid for scan speed.
- Type scale is tight, usually 1.125-1.2, and whitespace is discipline rather than feature.

**Default token postures:**
- `spacing.base = 4pt`
- `spacing.scale = [4, 8, 12, 16, 20, 24, 32]`
- `type.body.size = 13pt`
- `type.body.leading = 1.45x`
- `row.height = 28-32pt`

**Default anti-patterns:**
- Padding so generous that a row exceeds 56pt; that is sparse, not dense.
- More than one accent color competing for attention in repeated content.
- Dense panels without visible grouping, sticky headers, or selection state.

**Pairs naturally with:**
- `topology: list-detail` or `topology: multi-region`
- `expressiveness: restrained`
- `motion: calm` or `motion: standard`
- `trust: professional` or `trust: enterprise`

**Conflicts with:**
- `topology: single-pane` because it wastes the density.
- `expressiveness: expressive` because dense plus expressive quickly becomes visual chaos.
- Consumer onboarding, premium editorial reading, and brand launch pages.

## Topology

### topology: single-pane

**Means at runtime:**
- One region dominates the page, frame, slide, or application study.
- Secondary navigation, metadata, and actions are visually subordinate and do not compete with the main object.
- The layout should still expose the next step or next section, but not as an equal peer.

**Default token postures:**
- `layout.columns = 1`
- `content.max_width = 680-960px`
- `primary.region.area >= 65%`
- `secondary.actions = inline, trailing, or below-primary`

**Default anti-patterns:**
- Fake single-pane pages that are really scattered card grids.
- Hiding required filters or state behind vague overflow controls.
- Centering every element so hierarchy depends only on font size.

**Pairs naturally with:**
- `density: sparse`
- `platform: marketing`
- `expressiveness: balanced` or `expressiveness: expressive`
- `motion: calm`

**Conflicts with:**
- `density: dense`
- Operator queues, observability dashboards, and multi-source analytics.
- `trust: enterprise` workflows where audit state must be visible.

### topology: list-detail

**Means at runtime:**
- A repeated collection and a selected object or work area are visible in relationship.
- Selection, focus, and active row state are persistent and unambiguous.
- On smaller screens the topology may collapse into drill-in navigation, but the conceptual relationship remains list first, detail second.

**Default token postures:**
- `list.width = 280-420px` on desktop web or native.
- `detail.min_width = 1.5x list.width`
- `row.height = 28-44pt` depending on density.
- `selection.indicator = persistent background, border, or leading rail`

**Default anti-patterns:**
- Equal-width panes where the system does not reveal whether list or detail is primary.
- Card grids posing as review queues.
- Detail panes that lose context after an action completes.

**Pairs naturally with:**
- `density: balanced` or `density: dense`
- `trust: professional`
- `platform: web-app` or `platform: native`
- `motion: standard`

**Conflicts with:**
- `platform: marketing`
- Logo-only brand identity work unless expressed as application-suite navigation.
- `density: sparse` when the workflow requires simultaneous comparison.

### topology: multi-region

**Means at runtime:**
- Several coordinated regions are visible together, such as charts, filters, logs, summaries, maps, timelines, or detail panels.
- Regions must share state, time range, filters, or narrative purpose rather than merely filling space.
- One region remains dominant; the largest content region should be at least 1.5x the second-largest unless the medium explicitly requires small multiples.

**Default token postures:**
- `layout.grid = 12 columns or named regions`
- `gutter = 16-24pt`
- `region.header.height = 28-40pt`
- `pane.dominance.min_ratio = 1.5`

**Default anti-patterns:**
- Equal-weight KPI grids with no action path.
- Uncoordinated charts with different filters or time ranges.
- Tiny panels that make every region unreadable.

**Pairs naturally with:**
- `density: dense`
- `trust: professional` or `trust: enterprise`
- `expressiveness: restrained`
- `platform: web-app`

**Conflicts with:**
- `trust: consumer` unless the product category naturally requires comparison.
- `expressiveness: expressive` when color and motion compete across regions.
- `platform: marketing` first-viewport storytelling.

## Expressiveness

### expressiveness: restrained

**Means at runtime:**
- The surface communicates through alignment, hierarchy, typography, state, and precise interaction more than decoration.
- Accent color is rare and semantic, not ornamental.
- Imagery and illustration appear only if they carry domain evidence or clarify a state.

**Default token postures:**
- `accent.count = 1`
- `surface.palette = neutral plus semantic states`
- `radius = 4-8px`
- `type.scale.ratio = 1.125-1.2`
- `illustration.required = false`

**Default anti-patterns:**
- Anonymous gray UI with no hierarchy or material detail.
- Accent color used for every clickable object.
- Decorative gradients, bokeh, or abstract shapes in task surfaces.

**Pairs naturally with:**
- `density: dense`
- `topology: list-detail` or `topology: multi-region`
- `trust: professional` or `trust: enterprise`
- `motion: calm`

**Conflicts with:**
- Public launch pages asking for a visibly distinctive brand moment.
- `motion: expressive` unless isolated to rare state changes.
- Consumer products whose differentiation depends on personality.

### expressiveness: balanced

**Means at runtime:**
- The system has a recognizable point of view without making every component a brand moment.
- Color, type, shape, image, and iconography are controlled enough for repeated use.
- The composition should feel authored but still preserve ordinary task speed.

**Default token postures:**
- `accent.count = 2-3`
- `surface.palette = neutral plus controlled brand tints`
- `radius = 6-12px`
- `type.scale.ratio = 1.2-1.25`
- `image.or.illustration = optional but governed`

**Default anti-patterns:**
- Two unrelated expressive systems competing in one surface.
- Brand color applied to every card, badge, and chart without semantic roles.
- Generic SaaS polish with no domain signal.

**Pairs naturally with:**
- `density: balanced`
- `topology: single-pane` or `topology: list-detail`
- `trust: consumer` or `trust: professional`
- `motion: standard`

**Conflicts with:**
- `trust: enterprise` when risk states need strict restraint.
- `density: dense` if brand treatments reduce scan speed.
- Premium editorial work that needs a more intentionally quiet posture.

### expressiveness: expressive

**Means at runtime:**
- Personality is a primary part of the deliverable, visible through display type, color, imagery, motion, theme, or composition.
- The first read should be memorable and domain-specific, not merely usable.
- Expressiveness still needs a system: repeated components, states, and pages must share clear rules.

**Default token postures:**
- `accent.count >= 3` only when each role is named.
- `display.type = allowed`
- `image.asset.required_for_public_surfaces = true`
- `radius = 8-20px` unless the brand demands sharper geometry.
- `motion.personality = allowed with reduced-motion fallback`

**Default anti-patterns:**
- Novelty that does not relate to the project domain or audience.
- Saturated one-hue palettes with no functional hierarchy.
- Motion, color, and type all shouting at once in a dense workflow.

**Pairs naturally with:**
- `platform: marketing`
- `trust: consumer`
- `motion: expressive`
- `density: sparse` or `density: balanced`

**Conflicts with:**
- `density: dense`
- Safety-critical, financial, security, or compliance-heavy enterprise surfaces.
- Document typography that must foreground source credibility.

## Motion

### motion: calm

**Means at runtime:**
- Motion exists primarily to maintain orientation, soften state changes, or avoid abruptness.
- Nothing loops, pulses, or distracts while the user is reading, comparing, or typing.
- In video and presentation, calm means measured pacing with enough hold time to inspect the content.

**Default token postures:**
- `motion.duration.short = 120ms`
- `motion.duration.base = 180ms`
- `motion.duration.long = 260ms`
- `motion.easing = ease-out`
- `ambient.motion = none`

**Default anti-patterns:**
- Looping decorative animations in a work surface.
- Slow transitions that block repeated actions.
- Calm motion used as an excuse for no focus, loading, or state feedback.

**Pairs naturally with:**
- `expressiveness: restrained`
- `density: dense`
- `trust: professional`
- `platform: native`

**Conflicts with:**
- Product videos, launch sites, or game UI moments that need visible energy.
- `expressiveness: expressive` if the brief expects delight or drama.
- Rapid monitoring states where feedback must be immediate.

### motion: standard

**Means at runtime:**
- Motion communicates control feedback, navigation, data updates, or state change without becoming a brand performance.
- Timings should feel crisp enough for repeated use and slow enough to be perceptible.
- Platform defaults are preferred when a native convention exists.

**Default token postures:**
- `motion.duration.short = 90ms`
- `motion.duration.base = 150ms`
- `motion.duration.long = 220ms`
- `motion.easing = platform-standard or cubic-bezier documented by state`
- `reduced.motion = equivalent non-motion state`

**Default anti-patterns:**
- No feedback for submitted, saving, filtering, or selected states.
- Mixing unrelated easing curves across similar interactions.
- Functional transitions that reflow layout or cause target jumps.

**Pairs naturally with:**
- `density: balanced`
- `topology: list-detail`
- `platform: web-app`
- `trust: professional`

**Conflicts with:**
- `platform: marketing` launch sections that need intentional choreography.
- `motion: calm` native experiences that should follow OS conventions exactly.
- `motion: expressive` game or video work where timing is part of the identity.

### motion: expressive

**Means at runtime:**
- Timing, easing, sequence, camera movement, or state animation is part of the aesthetic signature.
- Motion can create delight, anticipation, hierarchy, or narrative emphasis.
- Expressive motion must be bounded to moments that matter and must have reduced-motion alternatives.

**Default token postures:**
- `motion.duration.short = 120ms`
- `motion.duration.base = 240ms`
- `motion.duration.long = 480ms`
- `motion.easing = named custom curves`
- `motion.sequence = documented for hero, reveal, reward, or transition moments`

**Default anti-patterns:**
- Decorative motion on every hover or scroll event.
- Animation that delays task completion.
- No reduced-motion fallback for vestibular or accessibility-sensitive users.

**Pairs naturally with:**
- `expressiveness: expressive`
- `platform: marketing`
- `trust: consumer`
- `game_ui` and `video_animation` medium extensions

**Conflicts with:**
- `density: dense`
- `trust: enterprise`
- High-pressure operator consoles, financial approvals, and safety workflows.

## Platform

### platform: web-app

**Means at runtime:**
- The deliverable is browser-native or web-distributed, with responsive constraints, DOM/CSS implementation, and keyboard/pointer behavior.
- Focus states, URL/deep-link expectations, loading states, and component tokens are part of the contract.
- Visual choices must survive across standard desktop and mobile browser widths when the medium requires responsive behavior.

**Default token postures:**
- `breakpoints = [mobile, tablet, desktop, wide]`
- `focus.visible = required`
- `component.states = hover, focus, active, disabled, loading, error`
- `token.source = CSS or design-token JSON`

**Default anti-patterns:**
- Native-looking controls that do not behave like the OS or the web.
- Pixel-perfect desktop mockups with no responsive contract.
- Marketing sections reused inside work surfaces without density changes.

**Pairs naturally with:**
- `density: balanced` or `density: dense`
- `topology: list-detail` or `topology: multi-region`
- `trust: professional`
- `motion: standard`

**Conflicts with:**
- `platform: native` expectations such as dynamic type and OS navigation.
- Pure brand identity work that needs lockup and application rules first.
- Print-first document typography where pagination governs design.

### platform: native

**Means at runtime:**
- The deliverable follows an operating system or native framework idiom.
- Dynamic type, safe areas, system materials, platform navigation, accessibility settings, and expected gestures matter.
- Cross-platform work must state which conventions are intentionally shared and which are platform-specific.

**Default token postures:**
- `type = system text styles or mapped native scale`
- `spacing = platform-native increments`
- `safe_area = required`
- `navigation = platform idiomatic`
- `accessibility.size_classes = required`

**Default anti-patterns:**
- Web dashboards wrapped in a native shell with no native interaction changes.
- Custom controls that break expected accessibility or gesture behavior.
- Ignoring platform status bars, safe areas, or desktop window chrome.

**Pairs naturally with:**
- `motion: calm` or `motion: standard`
- `density: sparse` or `density: balanced`
- `trust: consumer` or `trust: professional`
- `topology: list-detail`

**Conflicts with:**
- `platform: marketing` persuasion layouts.
- Web-only token extraction or CSS-only parity checks.
- Heavy expressive motion that violates OS expectations.

### platform: marketing

**Means at runtime:**
- The deliverable optimizes for first impression, persuasion, recognition, narrative, and conversion rather than repeated expert throughput.
- The first viewport, first frame, or first slide must establish the product, place, brand, or offer clearly.
- Visual assets, composition, and copy hierarchy carry more of the experience than controls do.

**Default token postures:**
- `hero.asset = required for websites and videos`
- `display.type = allowed`
- `section.rhythm = viewport-led`
- `primary.cta = visually dominant`
- `density = sparse or balanced by default`

**Default anti-patterns:**
- Generic gradient hero pages with no real product, place, or object signal.
- Admin-card layouts on public brand surfaces.
- Hero text trapped inside a card when the page needs an immersive first read.

**Pairs naturally with:**
- `expressiveness: balanced` or `expressiveness: expressive`
- `motion: calm` or `motion: expressive`
- `density: sparse`
- `trust: consumer` or `trust: professional`

**Conflicts with:**
- `density: dense`
- `trust: enterprise` operator workflows.
- Native UI conventions unless the marketing surface is specifically an app-store or product-preview asset.

## Trust

### trust: consumer

**Means at runtime:**
- The experience earns trust through approachability, clear affordances, friendly pacing, and recovery from mistakes.
- Jargon is limited, error states explain next steps, and the design should not feel like internal tooling.
- Accessibility and legibility matter because the audience may be broad and untrained.

**Default token postures:**
- `contrast = AA minimum`
- `radius = 8-16px`
- `copy = plain-language`
- `states = forgiving empty, loading, success, and error treatments`
- `accent = can carry warmth or personality`

**Default anti-patterns:**
- Dense tables as the first experience for casual users.
- Enterprise risk language in ordinary consumer tasks.
- Decorative playfulness that hides pricing, privacy, or consequence.

**Pairs naturally with:**
- `expressiveness: balanced` or `expressiveness: expressive`
- `density: sparse` or `density: balanced`
- `platform: native` or `platform: marketing`
- `motion: calm` or `motion: expressive`

**Conflicts with:**
- `density: dense`
- `topology: multi-region` unless comparison is central to the product.
- High-pressure regulated workflows.

### trust: professional

**Means at runtime:**
- The experience earns trust through competence, consistency, evidence, and clear user control.
- Surfaces can be information-rich, but hierarchy and state must remain immediately legible.
- Copy should name concrete objects, systems, and actions rather than generic placeholders.

**Default token postures:**
- `contrast = AA required`
- `radius = 4-10px`
- `accent = semantic and restrained`
- `metadata = visible for decisions`
- `tables.charts = aligned and source-labeled`

**Default anti-patterns:**
- Marketing hero scale inside repeated workflow panels.
- Generic nouns such as Item, Record, or Status as the main IA labels.
- Charts without source, units, time window, or annotation.

**Pairs naturally with:**
- `density: balanced`
- `topology: list-detail`
- `expressiveness: restrained` or `expressiveness: balanced`
- `platform: web-app`

**Conflicts with:**
- `expressiveness: expressive` when it weakens evidence or task speed.
- `platform: marketing` for internal workbench screens.
- Vague workflow verbs like Edit, Save, or Update as primary actions.

### trust: enterprise

**Means at runtime:**
- The experience earns trust through auditability, permission clarity, risk signaling, accessibility, and predictable interaction.
- Destructive, financial, security, compliance, or bulk actions must be nested and unambiguous.
- Every important state should have a label, source, timestamp, or owner when the domain calls for it.

**Default token postures:**
- `contrast = AA required; AAA preferred for dense body text`
- `radius = 2-8px`
- `status.tokens = explicit color plus label plus icon or text`
- `danger.actions = nested and confirmable`
- `audit.metadata = visible`

**Default anti-patterns:**
- Color-only risk states.
- Playful motion or copy around consequential actions.
- Equal-weight dashboards where no primary risk, queue, or exception is visible.

**Pairs naturally with:**
- `density: dense`
- `topology: multi-region`
- `expressiveness: restrained`
- `platform: web-app`

**Conflicts with:**
- `expressiveness: expressive`
- `platform: marketing`
- Hidden metadata, ambiguous ownership, and unqualified status language.
