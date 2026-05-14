---
type: aesthetic-preset
name: apple_consumer
description: Apple.com-style consumer product aesthetic - sparse, single-pane, expressive, expressive motion, marketing, consumer.
axes:
  density: sparse
  topology: single_panel
  expressiveness: expressive
  motion: expressive
  platform: web_native
  trust: approachable
applies_to_mediums:
  - medium: web_ui
    applicability: primary
  - medium: native_ui
    applicability: primary
  - medium: presentation
    applicability: secondary
adjacent_presets: [vercel_marketing, editorial_premium]
version: "1.0"
last_validated: "2026-05-10T14:04:06-04:00"
clip_centroid_path: vault/archive/visual-aesthetics/centroids/apple_consumer.npy
---

# apple_consumer

Apple.com-style consumer product aesthetics are for polished public surfaces
where a product, place, object, or offer must feel immediately tangible and
desirable. The layout is sparse, single-minded, product-forward, and expressive
without becoming noisy.

Human aliases:

- `topology: single_panel` = single-pane.
- `platform: web_native` = marketing web.
- `trust: approachable` = consumer.

The signature is confidence through restraint: huge product signal, strong
typography, precise spacing, immersive imagery, scroll-led reveal, and copy
that says less but lands harder.

## Applies to mediums

Primary:

- `web_ui`: Public product pages, launch pages, hero-led marketing sites,
  consumer landing pages, portfolio/product-object pages, premium object
  storytelling, conversion pages where the product itself is the visual anchor.
- `native_ui`: Native consumer app concept screens when Apple-like sparseness
  and platform polish are desired. Use native controls and avoid web marketing
  chrome.

Secondary:

- `presentation`: Keynote-like product narratives, launch decks, and investor
  story slides where one idea per slide and large product visuals dominate.

Do not use this preset for dense operator tools, enterprise admin systems,
document-heavy reports, or data consoles.

## When to pick this

Pick `apple_consumer` when the brief contains these signals:

- The page is public-facing and first-impression quality matters.
- The product, object, venue, or brand should be visible in the first viewport.
- The brief references Apple, apple.com, product launches, product pages,
  premium consumer, cinematic scroll, or hero product imagery.
- The desired emotional posture is polished, aspirational, confident, and
  simple.
- The conversion job depends on the audience understanding the product in under
  five seconds.
- The design should avoid generic SaaS dashboards and instead create a product
  story.

Strong matching phrases:

- "Apple-style"
- "apple.com"
- "premium consumer"
- "product launch"
- "hero product page"
- "cinematic product reveal"
- "immaculate spacing"
- "big product imagery"
- "sparse but expressive"

## When NOT to pick this

Anti-signals:

- The primary surface is a dashboard, admin panel, or operator console. Consider
  `operator_triage` or `operator_admin`.
- The product requires dense comparison tables and enterprise workflows.
- The brief needs editorial long-form reading more than product storytelling.
  Consider `editorial_premium`.
- The audience is developers and the page needs technical density. Consider
  `developer_tools` or `vercel_marketing`.
- The page is a native settings/preferences surface. Consider `apple_native`.
- The design must use playful social-app energy. Consider `playful_consumer`.

Adjacent presets to consider:

- `vercel_marketing`: choose when the product is developer/platform SaaS and
  needs sharper technical proof, code snippets, or startup launch energy.
- `editorial_premium`: choose when copy, photography, and publication rhythm
  matter more than a product-object reveal.

## Default reference pack

Use Apple public pages that `agent-browser` can capture. Prefer current product
pages that show large imagery and section rhythm.

Web UI primary references:

1. `https://www.apple.com/iphone/`
   - Capture product-forward hero hierarchy, large type, imagery, and section
     cadence.
2. `https://www.apple.com/apple-vision-pro/`
   - Capture immersive product storytelling and restrained navigation.
3. `https://www.apple.com/macbook-pro/`
   - Capture technical product proof rendered with consumer polish.
4. `https://www.apple.com/ipad-pro/`
   - Capture sparse product reveal, motion-ready composition, and dark/light
     section transitions.
5. `https://www.apple.com/watch/`
   - Capture lifestyle/product pairing and compact claim rhythm.

Native UI primary references:

1. `https://developer.apple.com/design/human-interface-guidelines/`
   - Use for platform taste constraints when this preset is applied to native
     screens.
2. `https://www.apple.com/ios/`
   - Capture consumer-native feature framing and platform surface polish.

Presentation secondary references:

1. `https://www.apple.com/apple-events/`
   - Capture keynote-like pacing, large visual anchors, and product reveal
     sequencing.

Reference interpretation:

- Borrow scale, restraint, section rhythm, and product object primacy.
- Do not copy Apple product imagery, trademarked copy, icons, or interaction
  patents.
- Replace Apple-specific product language with the project's literal offer.

## Default anti-pattern pack

Anti-pattern URLs are drift boundaries:

1. `https://www.amazon.com/s?k=iphone`
   - Avoid retail grid density, price-first hierarchy, and crowded commerce
     chrome when the brief asks for premium product storytelling.
2. `https://www.bestbuy.com/site/mobile-cell-phones/iphone/pcmcat305200050000.c`
   - Avoid SKU-grid comparison posture for a product launch page.
3. `https://getbootstrap.com/docs/5.3/examples/heroes/`
   - Avoid generic split hero/card examples and placeholder hero structure.
4. `https://www.samsung.com/us/smartphones/`
   - Use carefully as an adjacent consumer reference; avoid feature-grid
     over-density if the selected direction is explicitly Apple-like.

Presentation anti-patterns:

1. `https://slidesgo.com/`
   - Avoid decorative template slides, repeated shape motifs, and stock
     illustration filler.

## Default token postures

Color:

- Light background: `#F5F5F7`.
- Pure white surface: `#FFFFFF`.
- Dark section background: `#000000` or `#111111`.
- Text primary on light: `#1D1D1F`.
- Text secondary on light: `#6E6E73`.
- Text primary on dark: `#F5F5F7`.
- Text secondary on dark: `#A1A1A6`.
- Accent link: `#0066CC`.
- Accent link hover: `#004F9F`.
- Divider subtle: `#D2D2D7`.
- Product-neutral gray: `#86868B`.
- Avoid multiple saturated accents.

Type:

- Font family: `SF Pro Display`, `SF Pro Text`, `-apple-system`,
  `BlinkMacSystemFont`, `Segoe UI`, sans-serif.
- Hero eyebrow: `21px` / `28px`, weight 600.
- Hero title desktop: `56px` to `72px`, line-height `1.05`, weight 600.
- Hero title mobile: `40px` to `48px`, line-height `1.08`, weight 600.
- Section headline: `40px` to `56px`, line-height `1.08`, weight 600.
- Feature headline: `28px` to `36px`, line-height `1.12`, weight 600.
- Body: `17px` / `25px`, weight 400.
- Small caption: `12px` / `16px`, weight 400.
- CTA/link: `17px` / `24px`, weight 400 or 500.
- Letter spacing: `0`; do not use negative tracking.

Spacing and density:

- Hero min height: `78vh` to `92vh`, leaving a hint of next section.
- Section vertical padding: `88px` to `140px` desktop.
- Mobile section padding: `56px` to `88px`.
- Max text width for hero support copy: `640px`.
- Product image max width: `min(100%, 1200px)`.
- CTA gap: `20px`.
- Feature grid gap when needed: `24px` to `32px`.
- Avoid dense card decks above the fold.

Radius:

- Large media masks: `18px` to `28px` only when the product image is framed.
- Buttons: pill shape is acceptable for Apple-like CTAs.
- Small chips: `999px`.
- Cards, if used: `14px` to `20px`, but avoid card-heavy composition.

Elevation:

- Most surfaces are flat.
- Product imagery provides depth.
- Use no routine box shadows.
- If a floating panel is needed: `0 16px 48px rgba(0,0,0,0.16)`.

Motion:

- Scroll reveal duration: `360ms` to `700ms`.
- Section fade/translate: subtle, 12px to 32px travel.
- Product transform/reveal: expressive but tied to scroll or clear user action.
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)`.
- Do not hide content by default if JS fails.

Focus:

- Web focus ring must remain visible, even on minimal CTA/link styling.
- Interactive media controls need labels and keyboard access.
- Reduced-motion mode should disable nonessential transforms.

## Component postures

Hero:

- H1 should be the product, place, object, or literal offer/category.
- Supporting copy carries the value proposition.
- The product must be visible or strongly implied in the first viewport.
- Do not put the hero copy inside a card.
- Avoid split text/media where the image is just a side card; use immersive
  product imagery or full-bleed composition.

Navigation:

- Minimal, low-height, product/brand visible.
- Avoid admin nav density and heavy sidebars.
- Primary CTA can appear in nav but should not dominate the hero.

Sections:

- One dominant idea per section.
- Large imagery or media carries proof.
- Copy is short and literal.
- Feature grids are secondary and should not become generic card soup.

CTAs:

- Use short labels: "Buy", "Learn more", "Get started", "View pricing".
- Primary and secondary CTA hierarchy should be obvious.
- Links can use chevrons if the codebase already uses an icon system.

Native UI primary:

- Apply sparseness and polish to native concept screens, but preserve platform
  controls.
- Do not build a web marketing page inside a native app frame.

Presentation secondary:

- One claim per slide.
- Large product image or diagram.
- Minimal text, no decorative template motifs.

## Forbidden drifts

- **Generic SaaS split hero:** headline left, boxed dashboard card right, no real
  product signal.
- **Gradient wallpaper hero:** a gradient substitutes for actual product,
  object, or media.
- **Stock atmosphere:** dark blurred image with text that does not reveal the
  product.
- **Feature-card carpet:** a grid of equal cards replaces product story.
- **Retail SKU grid:** price/comparison grid appears before the product story.
- **Tiny brand signal:** product name only appears in nav and not first-viewport
  content.
- **Overlong hero copy:** headline carries value prop paragraphs instead of a
  crisp product/category name.
- **Decorative motion:** scroll effects move without explaining product value.
- **One-note monochrome:** the page becomes only gray/black without product or
  material interest.
- **Accessibility sacrifice:** hidden content, invisible focus, or motion-only
  comprehension.

## Validation history

- 2026-05-10T14:04:06-04:00: Created for Visual Specification System Batch 12.
  Frontmatter validated against `schemas/aesthetic-preset.schema.json`.
  Reference pack selected from real Apple public pages and practical
  retail/template drift boundaries. Centroid path reserved at
  `vault/archive/visual-aesthetics/centroids/apple_consumer.npy`; compute after
  reference PNG capture.
