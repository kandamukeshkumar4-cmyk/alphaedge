# Loop V78 — Polymarket-style alert notification (Apple-grade, real imagery)

## What the user wants (verbatim intent + two reference screenshots)
Redesign the signal alert notification (frontend/src/components/AlertToast.tsx,
its animations in src/app/globals.css) to look like **Polymarket's mobile
alert cards**. Reference layout from the user's two examples:

  ┌────────────────────────────────────────────┐
  │ [category icon]  IPOS/2028   (small label)  │
  │ **Bold market question, up to 2 lines**     │
  │  (avatar) Name ───────   2.50x   [ 39% ]    │
  │  (avatar) Name ───────   1.39x   [ 67% ]    │
  │  $52,617,317 vol            38 markets      │
  └────────────────────────────────────────────┘

Key elements from the screenshots:
- Rounded-2xl dark card, generous padding, soft border, subtle depth.
- Top row: a small square **category/market icon** (real image) + a tiny
  uppercase label (e.g. "2028", "IPOS").
- **Bold market question** as the headline (real title, 2-line clamp).
- 1-2 outcome rows, each: a small **circular entity avatar** (real image —
  candidate face, company logo), the outcome name with a colored underline
  accent, a multiplier (e.g. 2.50x), and a **rounded % pill** on the right.
- Footer: volume (left) + market count / time (right), muted.
- If the market is about a person (e.g. **Elon Musk**), their photo appears as
  the avatar, sourced from a PUBLIC image (the venue's own image/icon fields —
  Polymarket Gamma returns `image` and `icon` per market/outcome; our DB
  already stores `image_url` and `icon`).

## Dimensions + motion = "Apple"
- Apple-notification proportions: comfortable padding, ~14-16px radius on
  avatars/pills, clear type hierarchy, tabular numerals for %/x/vol.
- Motion like iOS: a smooth spring/ease slide-and-settle on enter (not a
  harsh slide), a gentle scale-in (0.96 -> 1), content fading up slightly
  staggered; soft dismiss. Use cubic-bezier easing already in globals.css as
  the base; add a spring-like settle. Keep the draining lifetime bar but make
  it subtle. ALL motion gated by prefers-reduced-motion.

## Tickets (one commit each, feat(loop78): <ticket>) + tests
- N1 Data: extend the alert payload/hook (src/hooks/useSignalAlerts.ts) and,
  if needed, the backend alerts feed (backend/app/api/v1/alerts_feed.py) to
  carry: market icon/image url, up to 2 top outcomes each with {name, price,
  optional avatar image url}, volume, market/outcome count. Pull from REAL
  stored data (Market.image_url/icon, outcomes) — NEVER fabricate a face or a
  number; omit an avatar gracefully (fall back to the signal glyph token) when
  no image exists. Respect the leakage/paper rules (this is display only).
- N2 Image handling: next/image (or a safe <img> with onError fallback) for
  avatars/icons; whitelist the venue image hosts in next.config
  (images.remotePatterns) — polymarket/gamma CDN + kalshi; on load error or
  missing url, render the initials/glyph fallback. Never hotlink arbitrary
  unvetted hosts; only the venues we ingest from.
- N3 Rebuild AlertToast.tsx to the Polymarket card layout above: category
  icon + label, bold 2-line question, outcome rows (avatar + name +
  underline + multiplier + % pill), muted footer (vol + count). Keep it
  informational (branded tints, never danger-red error styling). Keep "View"
  affordance (whole card tappable to /signals or the market).
- N4 Apple-grade motion in globals.css: spring settle on enter, staggered
  content fade-up, subtle lifetime bar, soft exit; reduced-motion safe.
- N5 Gate: typecheck, lint, vitest, build all green; a focused AlertToast
  test (renders real title not slug, renders avatar when url present + glyph
  fallback when absent, no danger-red classes). Counts in STATE.md.

## Constraints
- Follow frontend/.claude/CLAUDE.md design tokens (mint primary #00E8B0, blue
  secondary, dark surfaces). No new UI libraries.
- NEVER fabricate a person's image, an outcome price, a volume, or a count —
  real data or honest omission only. Paper-trading truth unaffected.
- Never touch order/trade mutation paths. Never push/merge.
Exit: N1-N5 DONE or BLOCKED in goals/loop-v78-notif-redesign/STATE.md.
