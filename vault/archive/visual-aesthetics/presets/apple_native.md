---
type: aesthetic-preset
name: apple_native
description: System Settings / native macOS-style aesthetic - sparse, list-detail, restrained, calm, native, consumer.
axes:
  density: sparse
  topology: list_detail
  expressiveness: restrained
  motion: subtle
  platform: desktop_native
  trust: approachable
applies_to_mediums:
  - medium: native_ui
    applicability: primary
adjacent_presets: [things_calm, apple_consumer]
version: "1.0"
last_validated: "2026-05-10T14:04:06-04:00"
clip_centroid_path: vault/archive/visual-aesthetics/centroids/apple_native.npy
---

# apple_native

Apple native is for macOS/iOS-style settings, preferences, utility, and system
surfaces. It is sparse, restrained, list-detail, and calm. It should feel like a
native Apple application, not a web admin dashboard wearing rounded corners.

Human aliases:

- `topology: list_detail` = list-detail.
- `motion: subtle` = calm.
- `platform: desktop_native` = native macOS.
- `trust: approachable` = consumer/native trust.

The signature is platform familiarity: sidebar categories, clear selected
state, grouped settings, native control shapes, patient spacing, and almost no
decorative visual noise.

## Applies to mediums

Primary:

- `native_ui`: macOS System Settings-style surfaces, Tauri/Electron apps that
  intentionally mimic native desktop settings, iOS/iPadOS settings-like flows,
  preference panes, account/security settings, local utility configuration,
  and consumer productivity tools.

This preset is not a primary fit for `web_ui`. If a browser app wants Apple-like
consumer marketing, use `apple_consumer`. If it wants a dense workbench, use
`operator_triage` or `operator_admin`.

## When to pick this

Pick `apple_native` when the brief contains these signals:

- The UI is a settings, preferences, account, privacy, notification, or system
  configuration surface.
- The product is native macOS/iOS or should feel like it belongs on macOS.
- Users adjust options, inspect permissions, choose defaults, manage privacy, or
  configure integrations.
- The brief references System Settings, macOS, iOS Settings, Apple HIG, native
  app, calm utility, or Things-like native restraint.
- The desired posture is consumer approachable, not enterprise admin.

Strong matching phrases:

- "System Settings"
- "macOS Settings"
- "native macOS"
- "preferences"
- "settings pane"
- "Apple native"
- "calm utility"
- "sidebar settings"
- "native controls"

## When NOT to pick this

Anti-signals:

- The page is public marketing or product storytelling. Consider
  `apple_consumer`.
- The surface is a dense operator queue or review workbench. Consider
  `operator_triage`.
- The surface is enterprise admin, billing, customer management, or risk.
  Consider `operator_admin`.
- The surface needs large charts, logs, or live observability. Consider
  `observability_console`.
- The project asks for playful onboarding, game UI, or editorial layout.
- The UI is web-first and cannot use native control idioms honestly.

Adjacent presets to consider:

- `things_calm`: even quieter, task/productivity-native, more focused on a
  personal work list than system settings.
- `apple_consumer`: more expressive and public-facing; choose for marketing
  pages or product storytelling.

## Default reference pack

Use public Apple support and developer pages capturable by `agent-browser`.
When possible, supplement with operator-provided screenshots of the target OS
version because native UI details change across releases.

Native UI primary references:

1. `https://support.apple.com/guide/mac-help/change-system-settings-mh15217/mac`
   - Capture System Settings sidebar/detail model and native grouping language.
2. `https://support.apple.com/guide/mac-help/find-options-in-system-settings-mh26783/mac`
   - Capture search/settings navigation behavior and category discovery.
3. `https://support.apple.com/guide/mac-help/change-appearance-settings-mchl52e1c2d2/mac`
   - Capture appearance preferences, control density, and grouped settings.
4. `https://support.apple.com/guide/mac-help/change-notifications-settings-mh40583/mac`
   - Capture notification settings structure and list/detail settings posture.
5. `https://developer.apple.com/design/human-interface-guidelines/`
   - Capture platform-level guidance and current native design constraints.

Secondary references:

1. `https://www.apple.com/macos/`
   - Use for platform tone and consumer-native positioning, not for settings
     layout.
2. `https://www.apple.com/ios/`
   - Use when the target is iOS-native rather than macOS-native.

Reference interpretation:

- Borrow native hierarchy, spacing, grouping, control posture, and restraint.
- Do not copy Apple proprietary icons, screenshots, or exact application
  layouts.
- Use target platform controls when implementation technology supports them.

## Default anti-pattern pack

Anti-pattern URLs are drift boundaries:

1. `https://getbootstrap.com/docs/5.3/examples/dashboard/`
   - Avoid web dashboard chrome, metric cards, and Bootstrap spacing.
2. `https://adminlte.io/themes/v3/pages/forms/general.html`
   - Avoid admin-template form density and boxed web panels.
3. `https://m3.material.io/components/navigation-drawer/overview`
   - Avoid Android Material navigation metaphors when targeting macOS.
4. `https://getbootstrap.com/docs/5.3/forms/overview/`
   - Avoid browser-default form styling and full-width web controls.

Native anti-pattern descriptions:

- Sidebar categories that look like web nav rather than native settings.
- Overuse of cards and shadows.
- Custom toggles that do not match platform controls.
- Huge marketing headings inside a preferences screen.

## Default token postures

Color:

- Window background: `#F5F5F7` light, `#1E1E1E` dark.
- Sidebar background: `#EFEFF1` light, `#252525` dark.
- Detail surface: `#FFFFFF` light, `#2C2C2E` dark.
- Group background: `#FFFFFF` light, `#3A3A3C` dark.
- Separator: `#D8D8DC` light, `#48484A` dark.
- Text primary: `#1D1D1F` light, `#F5F5F7` dark.
- Text secondary: `#6E6E73` light, `#A1A1A6` dark.
- Accent: system blue `#007AFF`.
- Accent hover/pressed: `#006EDB`.
- Danger: system red `#FF3B30`.
- Success: system green `#34C759`.
- Warning: system orange `#FF9500`.
- Focus ring: system accent at 45 percent alpha.

Type:

- Font family: `SF Pro Text`, `-apple-system`, `BlinkMacSystemFont`,
  `Segoe UI`, sans-serif.
- Sidebar item: `13px` / `18px`, weight 400 or 500 when selected.
- Group label: `12px` / `16px`, weight 500, muted.
- Setting title: `13px` / `18px`, weight 400.
- Setting description: `12px` / `16px`, weight 400.
- Pane title: `20px` / `28px`, weight 600.
- Button/control text: `13px` / `16px`, weight 400.
- Letter spacing: `0`.

Spacing and density:

- Window min width: `820px` for macOS settings-like surfaces.
- Sidebar width: `220px` to `260px`.
- Detail max width: `680px` to `760px`.
- Pane padding: `24px` to `32px`.
- Group vertical gap: `16px`.
- Group row height: `44px` to `52px`.
- Row horizontal padding: `14px` to `16px`.
- Sidebar item height: `28px` to `32px`.
- Control group gap: `8px` to `12px`.
- Footer/action area gap: `12px`.

Radius:

- Window/group radius: `10px` to `12px`.
- Sidebar selected item: `6px`.
- Buttons: platform default, approximate `6px`.
- Inputs/search: `8px`.
- Avoid oversized pill controls except system tokens or search fields.

Elevation:

- Native settings surfaces are mostly flat.
- Use group backgrounds and separators rather than shadows.
- Popovers/sheets may use native shadow:
  `0 12px 40px rgba(0,0,0,0.18)`.
- Avoid web-card elevation.

Motion:

- Focus/hover: `80ms` to `120ms`.
- Sidebar selection: immediate or `100ms`.
- Sheet/popover: `160ms` to `220ms`.
- Easing: platform default or `cubic-bezier(0.2, 0, 0, 1)`.
- Respect reduced motion.

Focus:

- Native focus ring when available.
- Keyboard navigation must traverse sidebar, search, settings groups, and
  controls in visual order.
- Search field should be reachable early.

## Component postures

Window/shell:

- Sidebar left, detail pane right.
- Optional toolbar/search at top.
- Avoid web-app top nav stacked above the native sidebar.
- Use platform titlebar conventions when implementation allows.

Sidebar:

- Category rows are compact with icons plus labels when icons exist.
- Selected row uses rounded fill, not a left color bar borrowed from web admin.
- Section ordering should match user mental model, not marketing priority.

Settings groups:

- Use rounded group containers or platform group lists.
- Each row has one primary setting and optional description.
- Toggle, select, button, or value sits on the trailing edge.
- Destructive actions are isolated and clearly labeled.

Forms:

- Keep forms short and grouped.
- Do not create long enterprise admin forms unless the project explicitly needs
  admin depth; then consider `operator_admin`.
- Validation language is calm and specific.

Native controls:

- Toggles should look like system toggles.
- Segmented controls are preferred for small mode sets.
- Steppers/sliders are preferred for numeric settings where appropriate.
- Menus are preferred for compact option sets.

## Forbidden drifts

- **Web admin in a native frame:** Bootstrap-like forms inside a macOS shell.
- **Marketing heading creep:** big hero headline inside a settings pane.
- **Card stack:** every setting group becomes a floating card with shadow.
- **Non-native toggles:** custom switches that fight platform expectations.
- **Sidebar-as-SaaS-nav:** heavy icons, badges, or route chrome in a settings
  sidebar.
- **Dense table import:** records tables dominate a preference surface.
- **Over-animated settings:** expressive motion where calm native transitions
  are expected.
- **Tiny inaccessible labels:** sparse does not mean 10px text.
- **Unclear grouping:** settings are listed without semantic groups or row
  hierarchy.
- **Web accent overload:** accent color used for backgrounds and decoration
  rather than selection and controls.

## Validation history

- 2026-05-10T14:04:06-04:00: Created for Visual Specification System Batch 12.
  Frontmatter validated against `schemas/aesthetic-preset.schema.json`.
  Reference pack selected from real Apple support/developer pages and concrete
  web-admin anti-pattern boundaries. Centroid path reserved at
  `vault/archive/visual-aesthetics/centroids/apple_native.npy`; compute after
  reference PNG capture.
