---
type: aesthetic-preset
name: operator_admin
description: Stripe-Dashboard-style administrative aesthetic - dense, list-detail, restrained, standard motion, enterprise.
axes:
  density: dense
  topology: list_detail
  expressiveness: restrained
  motion: functional
  platform: web_native
  trust: enterprise
applies_to_mediums:
  - medium: web_ui
    applicability: primary
  - medium: native_ui
    applicability: secondary
adjacent_presets: [operator_triage, fintech_precise]
version: "1.0"
last_validated: "2026-05-10T14:04:06-04:00"
clip_centroid_path: vault/archive/visual-aesthetics/centroids/operator_admin.npy
---

# operator_admin

Stripe-Dashboard-style operator admin is for enterprise web applications where
users administer customers, billing, payments, subscriptions, risk, identities,
workspaces, permissions, ledgers, or operational settings. It is dense and
functional, but slightly more formal than `operator_triage`.

Human aliases:

- `topology: list_detail` = list-detail.
- `motion: functional` = standard motion.
- `platform: web_native` = web-app.
- `trust: enterprise` = institutional admin trust.

The signature is precise control: explicit navigation, compact tables, clear
forms, subdued surfaces, semantic status color, and robust empty/loading/error
states.

## Applies to mediums

Primary:

- `web_ui`: Admin portals, customer dashboards, payments/billing dashboards,
  account consoles, enterprise SaaS back offices, risk tools, permission
  management, workflow administration, customer support consoles.

Secondary:

- `native_ui`: Native admin tools where the domain is still enterprise records,
  forms, and configuration. Preserve platform idiom while keeping the admin
  information architecture.

Use this when the product must feel reliable and institution-ready, not merely
fast and lightweight.

## When to pick this

Pick `operator_admin` when the brief contains these signals:

- Objects include customers, invoices, payments, subscriptions, disputes,
  ledgers, accounts, roles, API keys, organizations, seats, usage, risk, or
  compliance.
- The user edits configuration or administers a system rather than simply
  triaging a queue.
- The surface needs dense tables plus forms, detail drawers, audit trails,
  filters, exports, and dangerous actions.
- The brief references Stripe Dashboard, financial admin, B2B SaaS admin,
  enterprise console, or operational back office.
- Trust must feel enterprise-grade: legible, explicit, controlled, and
  auditable.

Strong matching phrases:

- "Stripe Dashboard"
- "admin console"
- "billing dashboard"
- "customer portal"
- "subscription management"
- "roles and permissions"
- "enterprise settings"
- "financial operations"
- "risk review"
- "audit log"

## When NOT to pick this

Anti-signals:

- The primary workflow is a fast issue/approval triage queue with minimal form
  depth. Consider `operator_triage`.
- The screen is a live observability wall or system metrics console. Consider
  `observability_console`.
- The product is a consumer landing page or product launch story. Consider
  `apple_consumer` or `vercel_marketing`.
- The work is standalone chart storytelling. Consider `executive_analytics` or
  `data_scientific`.
- The brief calls for playful consumer energy or editorial whitespace.
- The UI should look like native macOS Settings. Consider `apple_native`.

Adjacent presets to consider:

- `operator_triage`: closer to Linear; use when queue decisions and keyboard
  throughput are more important than forms and enterprise administration.
- `fintech_precise`: more finance-specific; use when numbers, statements,
  reconciliation, balances, and regulatory precision dominate.

## Default reference pack

Use public Stripe documentation and product pages that `agent-browser` can
capture without an authenticated dashboard session.

Web UI primary references:

1. `https://docs.stripe.com/dashboard/basics`
   - Capture dashboard concepts, sidebar/content relationships, and Stripe's
     explanatory framing for admin surfaces.
2. `https://docs.stripe.com/development/dashboard`
   - Capture developer/admin dashboard settings and environment-switching
     posture.
3. `https://docs.stripe.com/invoicing/dashboard`
   - Capture invoice list/detail workflows, financial object language, and
     status vocabulary.
4. `https://docs.stripe.com/connect/stripe-dashboard`
   - Capture connected account administration concepts and enterprise trust
     framing.
5. `https://stripe.com/docs`
   - Capture restrained typography, navigation density, and Stripe's broader
     information architecture.

Secondary references:

1. `https://stripe.com/radar`
   - Use for risk and fraud status language when relevant.
2. `https://stripe.com/billing`
   - Use for billing domain language and enterprise product framing.
3. `https://stripe.com/connect`
   - Use for multi-party account and platform administration posture.

Reference interpretation:

- Borrow precise tables, explicit forms, enterprise polish, and quiet status
  treatment.
- Do not copy Stripe branding, iconography, product names, or proprietary
  dashboard layouts.
- Use the project's domain vocabulary and data records.

## Default anti-pattern pack

Anti-pattern URLs are drift boundaries:

1. `https://getbootstrap.com/docs/5.3/examples/dashboard/`
   - Avoid generic dashboard scaffolding with large cards above a table and no
     domain-specific control model.
2. `https://adminlte.io/themes/v3/`
   - Avoid saturated admin template chrome, widget clutter, and heavy shadows.
3. `https://demos.creative-tim.com/material-dashboard/pages/dashboard`
   - Avoid decorative gradients, thick cards, and template-like metric panels.
4. `https://www.salesforce.com/products/sales-cloud/`
   - Avoid marketing-page density or CRM branding cues in a focused admin tool.

Native UI anti-patterns:

1. `https://m3.material.io/components/cards/overview`
   - Avoid turning enterprise records into oversized cards.
2. `https://getbootstrap.com/docs/5.3/forms/overview/`
   - Avoid default form styling without product-specific hierarchy.

## Default token postures

Color:

- Background: `#F7F9FC`.
- Surface base: `#FFFFFF`.
- Surface alternate: `#F6F8FA`.
- Surface inset: `#F1F4F8`.
- Border: `#D8DEE8`.
- Separator: `#E6EAF0`.
- Text primary: `#1A1F36`.
- Text secondary: `#4F566B`.
- Text tertiary: `#697386`.
- Accent: `#635BFF`.
- Accent hover: `#4B44D4`.
- Accent soft: `#F1EFFF`.
- Info: `#0A66C2`.
- Success: `#0E6245`.
- Warning: `#B76E00`.
- Danger: `#A41C1C`.
- Disabled surface: `#F3F4F6`.
- Disabled text: `#A3ACBA`.

Type:

- Font family: `Inter`, `SF Pro Text`, `-apple-system`, `BlinkMacSystemFont`,
  `Segoe UI`, sans-serif.
- Body: `13px` / `20px`, weight 400.
- Table row primary: `13px` / `18px`, weight 500.
- Metadata: `12px` / `16px`, weight 400.
- Label: `12px` / `16px`, weight 500.
- Page title: `20px` / `28px`, weight 600.
- Section title: `15px` / `22px`, weight 600.
- Numeric values: tabular figures, `13px` or `14px`, weight 500.
- Code/API key snippets: `12px` / `16px`, monospace.
- Letter spacing: `0`.

Spacing and density:

- Row height: `36px` default, `40px` for financial rows with two-line metadata.
- Table cell horizontal padding: `12px`.
- Form control height: `32px`.
- Button height: `30px` compact, `36px` primary in forms.
- Sidebar width: `236px` to `260px`.
- Content max width for settings forms: `920px`.
- Detail drawer width: `420px` to `560px`.
- Page content padding: `24px`.
- Section gap: `24px`.
- Field group gap: `16px`.
- Inline control gap: `8px`.

Radius:

- Small controls: `6px`.
- Input/select: `6px`.
- Panels: `8px`.
- Drawer/modal: `10px`.
- Badges: `999px` only for small status pills.

Elevation:

- Page panels: no shadow or `0 1px 2px rgba(26, 31, 54, 0.04)`.
- Dropdown: `0 8px 24px rgba(26, 31, 54, 0.12)`.
- Drawer/modal: `0 18px 50px rgba(26, 31, 54, 0.18)`.
- Avoid stacked shadows across normal content.

Motion:

- Hover/focus transitions: `100ms` to `140ms`.
- Drawer open: `160ms` to `200ms`.
- Toast enter/exit: `160ms`.
- Easing: `cubic-bezier(0.2, 0, 0, 1)`.
- Loading skeleton shimmer: permitted only for genuine loading states, muted.

Focus:

- Focus ring: `2px` accent outline with `2px` offset or inset ring when space is
  tight.
- Error focus: danger ring plus message text.
- Keyboard order must follow sidebar -> header controls -> table -> detail.

## Component postures

Shell:

- Sidebar navigation is explicit and sectioned. It may include workspace switch,
  environment/test mode, and account controls.
- Header contains breadcrumbs or page title plus search/actions.
- Avoid top-heavy hero blocks.

Tables:

- Tables are first-class. Use sticky header when rows scroll.
- Columns should have domain-specific labels, not generic "Name / Status /
  Action" when the brief gives better language.
- Numeric columns use tabular figures and right alignment when comparing money,
  counts, or rates.
- Selected rows need a clear background and left border or accent marker.

Forms:

- Labels above controls for complex forms; inline labels only for compact
  filters.
- Help text is concise and muted, not paragraph-heavy.
- Dangerous controls live in a distinct danger zone or confirmation flow.
- Required fields are explicit.

Status and badges:

- Status color is semantic and sparse.
- Use text plus color; never color alone.
- Badge height: `20px` to `22px`.

Detail drawers:

- Use for quick inspection and edits without losing table context.
- Include timestamp/audit metadata when domain trust requires it.
- Do not use drawer as a second homepage.

Native UI secondary:

- Preserve native navigation and forms, but keep enterprise record density.
- Avoid consumer preference-page sparseness when records and controls matter.

## Forbidden drifts

- **Generic KPI cap:** four metric cards at the top of every admin page.
- **Template sidebar saturation:** loud gradient sidebars or thick brand blocks.
- **Decorative fintech glow:** finance domain does not justify neon gradients.
- **Form swamp:** long forms without sectioning, help text, validation, or
  hierarchy.
- **Unlabeled icon actions:** enterprise admin actions need visible labels or
  tooltips and audit-safe wording.
- **Action ambiguity:** destructive, primary, and secondary actions look equal.
- **Status color overload:** five strong colors compete in one table.
- **Card grid admin:** records become equal-weight cards instead of scannable
  rows.
- **Fake enterprise:** adding badges and shadows without auditability,
  states, or real domain data.
- **Low-density settings drift:** page becomes a sparse preference panel rather
  than an admin work surface.

## Validation history

- 2026-05-10T14:04:06-04:00: Created for Visual Specification System Batch 12.
  Frontmatter validated against `schemas/aesthetic-preset.schema.json`.
  Reference pack selected from real Stripe public docs/product pages plus
  concrete admin-template anti-pattern boundaries. Centroid path reserved at
  `vault/archive/visual-aesthetics/centroids/operator_admin.npy`; compute after
  reference PNG capture.
