# Loop V78 — STATE

Exit status: **N1–N5 DONE** (one commit per ticket, on `loop78/notif-redesign`).

## Tickets

- **N1 DONE** — `6523c9c` feat(loop78): N1 — signals feed carries real market
  imagery/outcomes. `CLVTrackingService.get_signal_feed` batch-composes (2
  queries, no N+1) Market rows + latest OddsSnapshot YES price per slug;
  `SignalFeedItemResponse` gains additive optional `market_title, category,
  icon, image_url, volume, traders, market_count, outcomes[] {name, price,
  image_url}`. YES row carries the venue market image; NO row gets none
  (glyph fallback). Unmirrored slug → all None + `outcomes: []`; market with
  no snapshot → no outcome rows. Hook `useSignalAlerts` maps the new fields
  (`SignalAlert.marketSlug/categoryLabel/icon/imageUrl/volume/traders/
  marketCount/outcomes`), preferring real `market_title` over the slug.
  Backend alerts_feed.py untouched (toast polls `/signals/feed`).
- **N2 DONE** — `4876edc` feat(loop78): N2 — `src/lib/venue-images.ts` is the
  single allowlist module consumed by BOTH `next.config.ts`
  `images.remotePatterns` and the new `VenueImage` component runtime guard
  (plain `<img>` — the SWA deploy is `output: "export"`, no next/image
  optimizer; onError → glyph fallback, keyed per-src). Whitelist verified
  live 2026-07-20: Polymarket Gamma `image`/`icon` =
  `polymarket-upload.s3.us-east-2.amazonaws.com`. Kalshi trade API exposes NO
  market image field (verified live + in kalshi_live_ingest.py) → no Kalshi
  host exists to whitelist; Kalshi markets glyph-fallback by design.
- **N3 DONE** — `8ff1a8a` feat(loop78): N3 — AlertToast rebuilt to the
  Polymarket mobile card: square venue icon + tiny uppercase category label +
  signal kicker/glyph; bold 2-line-clamped real question; ≤2 outcome rows
  (circular avatar/glyph, name with mint/blue underline accent, `2.56x`
  multiplier, rounded % pill — Yes mint / No blue, NEVER danger-red); muted
  `$vol` + `N markets`/`N traders` footer. Whole card is the View link
  (`/markets/<slug>` when mirrored, else `/signals`). Split into pure
  `AlertToastCard` (SSR-testable) + timer container.
- **N4 DONE** — `55f8664` feat(loop78): N4 — spring-settle enter (24px/−6px
  travel + scale 0.96→1, `cubic-bezier(0.34,1.35,0.64,1)`, 0.55s), staggered
  section fade-up (`alert-toast-rise-1..4`, 50ms steps), soft fade/scale
  exit, drain bar kept but `opacity-60` subtle; dead `alert-toast-pulse`
  removed; reduced-motion kill-switch now also zeroes animation/transition
  delays so stagger can't hold content hidden.
- **N5 DONE** — gate proof below.

## Gate counts (N5)

- Focused: `AlertToast.test.tsx` 8/8 (real title not slug; slug humanized;
  avatar img when url present; glyph fallback when absent; non-venue host
  never hotlinked; % pill + multiplier + footer real numbers; honest
  omission; no danger/down classes).
- Frontend: typecheck PASS, lint PASS (`--max-warnings=0`), vitest
  **85 files / 500 tests PASS**, `next build` PASS.
- Backend: new `test_signal_feed_enrichment.py` 3/3 (+ feed-cache 4/4);
  ruff PASS.

`py -3.13 orchestration/gate.py` (full: backend pytest -x -q, backend ruff,
frontend typecheck, frontend test, frontend build):

```
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

## Never-watched

- No fabricated imagery/prices/volumes/counts — everything from stored
  Market/OddsSnapshot rows or honest omission (glyph fallback / omitted row).
- No danger-red error styling; tints stay primary/secondary/amber.
- No order/trade mutation paths touched. No push, no merge.

AutoLab: not applicable (one-shot UI redesign; gate is the measure).
