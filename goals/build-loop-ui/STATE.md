# UI Build Loop — Questflow design system (STATE)

Goal: complete the Questflow-style UI end-to-end so every shipped backend
feature (briefs, track record, signals, whales, live prices, paper trading)
is visible in the app. Design tokens live in `frontend/tailwind.config.ts`
(mint `#3ee6b0` on green-charcoal); components in `frontend/src/components/quest/`.
New UI should also respect `frontend/.claude/CLAUDE.md` (Astryx) where practical.

Gate (must stay green after every ticket):
- `npm run typecheck` · `npm run lint` · `npm test` (from `frontend/`)
- Page renders in preview without console errors

## Tickets

| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| U0 | Quest tokens + header + Discover home + onboarding | DONE 2026-07-03 | quest/* components, old tour removed |
| U1 | Discover **Feed tab** — merged briefs + signals timeline | DONE 2026-07-03 | QuestFeed.tsx; Markets/Feed tabs on home |
| U2 | `/markets` page → Quest card grid (retire Kalshi row design) | DONE 2026-07-03 | markets-client.tsx now renders QuestMarketsBoard (grid + topic filters + hero kept); Kalshi components left in tree but unmounted |
| U3 | Market detail → Quest trade terminal (chart + book + panel + analyst dock) | DONE 2026-07-03 | Quest-styled via retheme + QuestMarketRail (brief/track-record/latency dock) added to detail right column |
| U4 | "Why this brief?" panel on `/research/brief` (citations + claim + evidence layers) | DONE 2026-07-03 | QuestWhyBrief.tsx mounted on brief page; groups citations by signal layer, shows claim + grading |
| U5 | Auth pages restyle + signup → onboarding handoff | DONE 2026-07-03 | Quest tokens inherited via retheme; signup clears ae_quest_onboarding_v1 so tour fires post-signup |
| U6 | Alerts surface (backend route + `/alerts` page) | DONE 2026-07-03 | backend `app/api/v1/activity.py` (`GET /api/v1/alerts`, `GET /api/v1/signals/events`) + tests; frontend `/alerts` page with Dispatched/Engine-room tabs; bell icon in header |
| U7 | Whale/news activity feed on market detail | DONE 2026-07-03 | QuestMarketActivity.tsx (per-market signal events, hidden when empty) mounted in detail right rail; nav completeness: Forecast in top nav, Eval/Mirror/Alerts/Portfolio in mobile menu |
| U8 | Migrate quest/* components onto Astryx primitives | TODO | follow frontend/.claude/CLAUDE.md |

## Loop protocol
1. Pick first TODO ticket. 2. Implement smallest shippable slice.
3. Run gate; fix until green. 4. Mark DONE with date + notes. 5. Repeat.
Stop and reorganize after 3 consecutive no-progress iterations.

AutoLab: baseline=U0 verified (typecheck/lint/61 tests green) | benchmark=gate + preview render | iterations=see table | budget=session | outcome=in-progress
