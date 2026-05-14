---
type: aesthetic-preset
name: operator_triage
description: Linear-style operator triage aesthetic - dense, list-detail, restrained, calm.
axes:
  density: dense
  topology: list_detail
  expressiveness: restrained
  motion: subtle
  platform: web_native
  trust: professional
applies_to_mediums:
  - medium: web_ui
    applicability: primary
  - medium: native_ui
    applicability: secondary
adjacent_presets: [operator_admin, observability_console]
version: "1.0"
last_validated: "2026-05-10T14:04:06-04:00"
clip_centroid_path: vault/archive/visual-aesthetics/centroids/operator_triage.npy
---

# operator_triage

Linear-style operator triage is for high-throughput work queues where the user
needs to scan, select, decide, and move on. It is dense but not noisy, fast but
not frantic, and structured around a list-detail mental model.

Human aliases:

- `topology: list_detail` = list-detail.
- `motion: subtle` = calm.
- `platform: web_native` = web-app.

The signature is a restrained workbench: warm neutral surfaces, tight type,
single-purpose accent color, obvious selected state, keyboard-first affordance,
and detail panes that never fight the list for dominance.

## Applies to mediums

Primary:

- `web_ui`: Browser operator consoles, triage queues, review inboxes, issue
  systems, task command centers, QA queues, approval queues, evidence review,
  and multi-step operational tools.

Secondary:

- `native_ui`: Native desktop or mobile workbench surfaces that still behave
  like a queue plus detail inspector. Use native controls and platform spacing,
  but preserve the dense triage hierarchy.

Do not use this preset for consumer marketing, editorial storytelling, playful
onboarding, blank-state-heavy products, or dashboards where the primary job is
aggregate monitoring rather than item-by-item action.

## When to pick this

Pick `operator_triage` when the brief contains any of these signals:

- The user works from an inbox, queue, backlog, review list, issue list, or
  approval stream.
- The primary verb is triage, review, approve, reject, assign, route, resolve,
  comment, merge, label, or hand off.
- The surface should feel like Linear, not like a BI dashboard or generic admin
  template.
- Users return many times per day and value keyboard flow, persistent context,
  and clear selected state over large decorative panels.
- Rows, filters, search, command menu, detail inspector, comments, metadata, and
  state transitions are core.
- The screen must support 25+ visible work items or a high amount of visible
  metadata without becoming heavy.
- The trust posture is professional: calm confidence, not enterprise ceremony.

Strong matching phrases:

- "operator console"
- "triage queue"
- "task inbox"
- "issue review"
- "approvals"
- "handoff"
- "review workbench"
- "Linear-style"
- "keyboard-first"
- "dense but calm"

## When NOT to pick this

Anti-signals:

- The main experience is a KPI dashboard, live metrics wall, or incident
  observability surface. Consider `observability_console`.
- The product is financial admin, billing, customers, risk, or subscriptions
  with formal enterprise controls. Consider `operator_admin`.
- The page is a public first-impression marketing site. Consider
  `apple_consumer`, `vercel_marketing`, or `editorial_premium`.
- The user needs immersive consumer delight, large imagery, or narrative
  persuasion.
- The UI must look native to macOS/iOS preferences rather than web-native.
  Consider `apple_native`.
- The brief emphasizes charts more than decisions on individual records.
  Consider `executive_analytics`, `observability_console`, or
  `data_scientific`.

Adjacent presets to consider:

- `operator_admin`: choose when the work is still dense but needs stronger
  enterprise affordance, form-heavy pages, compliance language, billing or
  customer objects, and more explicit navigation.
- `observability_console`: choose when time-series data, alerts, system health,
  logs, and charts dominate the first screen.

## Default reference pack

Use these as default URLs for `agent-browser` captures. Capture at 1440 by 900
for `web_ui` unless the medium plugin overrides the viewport.

Web UI primary references:

1. `https://linear.app/`
   - Capture the product and marketing surface for typography restraint,
     neutral palette, accent discipline, and product-first positioning.
2. `https://linear.app/docs/triage`
   - Capture actual triage concept language and UI screenshots when visible.
     Use as the closest named behavior reference.
3. `https://linear.app/docs/display-options`
   - Capture density, list configuration, view controls, and display options.
4. `https://linear.app/docs/creating-issues`
   - Capture issue creation affordances, metadata treatment, and the way Linear
     describes work objects.
5. `https://linear.app/docs/default-team-pages`
   - Capture team-page navigation and list/detail hierarchy references.

Native UI secondary references:

1. `https://linear.app/mobile`
   - Use only if the project is native/mobile and the page is capturable.
2. `https://linear.app/docs/keyboard-shortcuts`
   - Capture keyboard-first mental model and command affordance expectations.
3. `https://linear.app/docs/notifications`
   - Capture dense notification semantics when the product has inbox work.

Reference interpretation:

- Borrow density, hierarchy, and interaction posture.
- Do not copy Linear's trademarked names, icons, logo, or product-specific
  layouts.
- Keep project data and domain language original.

## Default anti-pattern pack

Anti-pattern URLs are drift boundaries, not statements that these products are
bad. They name visual moves this preset should not accidentally inherit.

Web UI anti-patterns:

1. `https://getbootstrap.com/docs/5.3/examples/dashboard/`
   - Avoid generic Bootstrap sidebar-dashboard composition, oversized summary
     cards, and template-default spacing.
2. `https://adminlte.io/themes/v3/`
   - Avoid saturated admin-template chrome, stacked widget clutter, and heavy
     box shadows.
3. `https://trello.com/`
   - Avoid board/card-first topology when the brief calls for queue triage and
     detail review.
4. `https://monday.com/`
   - Avoid celebratory project-management color density when the product needs
     quiet operational focus.

Native UI anti-patterns:

1. `https://m3.material.io/components/cards/overview`
   - Avoid card-grid-first Android material composition for triage work.
2. `https://getbootstrap.com/docs/5.3/components/card/`
   - Avoid treating every record as a freestanding card.

## Default token postures

Use these as starting values. Adjust for brand constraints only when the brief
or operator-provided brand assets require it.

Color:

- Background: `#F7F6F3` or `#F8F7F4` warm neutral.
- Surface base: `#FFFFFF`.
- Surface raised: `#FAFAF8`.
- Border subtle: `#E6E2DA`.
- Separator: `#EDE9E1`.
- Text primary: `#1F2328`.
- Text secondary: `#687076`.
- Text tertiary: `#8B949E`.
- Accent: one color only, default `#5E6AD2`.
- Accent hover: `#4F5CC8`.
- Accent soft background: `#F0F1FF`.
- Selected row background: `#F4F3FF`.
- Focus ring: accent at 40 percent alpha.
- Success: `#2E7D32`, warning: `#B7791F`, danger: `#C62828`.

Type:

- Font family: `Inter`, `SF Pro Text`, `-apple-system`, `BlinkMacSystemFont`,
  `Segoe UI`, sans-serif.
- Body row text: `13px` / `18px`, weight 450.
- Metadata text: `12px` / `16px`, weight 400.
- Section label: `11px` / `14px`, weight 600, uppercase only for short labels.
- Page title: `18px` / `24px`, weight 600.
- Detail title: `20px` / `28px`, weight 600.
- Button text: `13px` / `16px`, weight 500.
- Letter spacing: `0`.

Spacing and density:

- Row height: `32px` default, `36px` maximum for complex rows.
- List item horizontal padding: `10px` to `12px`.
- Table cell vertical padding: `6px`.
- Primary pane gap: `12px`.
- Header height: `48px`.
- Sidebar width: `220px` to `248px`.
- List pane width: `38%` to `46%`.
- Detail pane width: remaining space, with optional right rail at `280px`.
- Section padding: `16px`.
- Dense control height: `28px`.
- Search input height: `30px`.

Radius:

- Small control: `5px`.
- List row selected state: `6px`.
- Popover/menu: `8px`.
- Panel radius: `8px` maximum.
- Avoid pill-shaped controls except tags and compact status chips.

Elevation:

- Default panels: no shadow; use border/separator.
- Popover shadow: `0 8px 24px rgba(31, 35, 40, 0.12)`.
- Modal shadow: `0 16px 48px rgba(31, 35, 40, 0.16)`.
- Hover should not add big shadows to rows.

Motion:

- Focus/hover transition: `80ms` to `120ms`.
- Panel open/close: `120ms` to `160ms`.
- Easing: `cubic-bezier(0.2, 0, 0, 1)`.
- Avoid decorative page-load animation.

Focus:

- Keyboard focus ring: `2px` outer or inset outline using accent alpha.
- Selected row and focus state must be distinguishable.
- Command affordance should be visible near search or global actions.

## Component postures

Web UI shell:

- Top bar stays quiet. It carries route title, search/command, and primary
  action. It does not become a marketing hero.
- Sidebar is compact and text-first. Icons can support labels but should not
  replace labels for primary navigation.
- Use one active route indicator and one selected work item indicator.

List rows:

- 32px target row height for simple work items.
- Primary label left; compact metadata and status inline.
- Secondary metadata should be lower contrast, not smaller than 11px.
- Selected row background must be visible but quiet.
- Hover state should be `background-color` or border tint, not shadow.

Detail pane:

- Header contains title, status, assignee/owner, and primary actions.
- Body prioritizes decision context: description, checklist, comments, evidence,
  history, or linked records.
- Use separators and section headers instead of nested cards.
- Danger actions stay low-frequency and visually contained.

Filters and search:

- Filter chips are compact, `24px` to `28px` high.
- Search is always reachable and keyboard-obvious.
- Empty filters should not expand into decorative blank panels.

Command/menu affordances:

- Use compact menu rows, keyboard shortcuts, and search-first behavior.
- Menu item height: `28px` to `32px`.
- Shortcut text: `11px` to `12px`, muted.

Native UI secondary:

- Preserve native focus, sidebar, segmented control, and toolbar idioms.
- Keep the triage list dominant.
- Use platform spacing but do not turn dense work into a sparse settings page.

## Forbidden drifts

- **Card soup:** replacing the queue/detail structure with equal-weight cards.
- **Metric rail cosplay:** adding KPI cards because dashboards usually have
  them when the user's job is item decisions.
- **Purple-blue gradient wash:** letting the accent become a dominant theme.
- **Decorative empty state:** using large illustrations or marketing copy in a
  workbench that needs records.
- **Template admin chrome:** thick colored sidebars, big shadows, widget grids,
  and heavy top nav from admin templates.
- **Unclear selected state:** hover, selected, and focused rows all look the
  same.
- **Fake density:** tiny text without enough hierarchy or hit area.
- **Over-boxing:** every section gets a card, border, radius, and shadow.
- **Hero title inside app:** route pages start with marketing hero treatment.
- **Unbounded accent:** more than one strong accent competes for primary action.

## Validation history

- 2026-05-10T14:04:06-04:00: Created for Visual Specification System Batch 12.
  Frontmatter validated against `schemas/aesthetic-preset.schema.json`.
  Reference pack selected from real Linear public pages and practical drift
  boundaries. Centroid path reserved at
  `vault/archive/visual-aesthetics/centroids/operator_triage.npy`; compute after
  reference PNG capture.
