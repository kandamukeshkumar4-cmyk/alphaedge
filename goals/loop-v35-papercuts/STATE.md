# loop-v35-papercuts — STATE

## LOOP LOG
| step | date | result | proof |
|------|------|--------|-------|
| U1 | 2026-07-15 | DONE — evidence-backed papercut list | prod sweep chromium 1280+375 dark+html.light; screenshots under `evidence/` |
| U2 | | | |
| U3 | | | |

## U1 Sweep notes
- Prod: https://alphaedge-frontend-three.vercel.app (READ-ONLY)
- Routes: `/` `/markets` market detail `/portfolio` `/leaderboard` `/signals` `/eval` `/alerts` `/feed`
- `/traders/<any>`: **unavailable** — leaderboard honest-empty (“No ranked traders yet”); feed has no `/traders/` links while logged out. Not invented.
- Theme toggle: **none in chrome**. `html.light` flips chart tokens only; body stays `rgb(7,11,10)` (dark-only redesign). Sweep still captured light residual shots.

## Papercut list (evidence-only; ranked by user impact)

| ID | Impact | Finding | Evidence |
|----|--------|---------|----------|
| PC01 | HIGH | Header search squeezed (~165px wrap / ~117px input at 1280). Placeholder `Search markets…  ( / )` (~135px) clips to `Search markets… (` | `evidence/PC01_search_crushed_header.png` |
| PC02 | HIGH | `/alerts` group headings render raw `pm-…` slugs (mono + truncate). Unreadable especially at 375 | `evidence/PC02_alerts_raw_slugs.png`, `evidence/PC02b_alerts_slugs_mobile.png` |
| PC03 | MED-HIGH | `/markets` has no `<h1>` landmark (only category `<h2>`). | `evidence/PC03_markets_no_h1.png` |
| PC04 | MED | `/eval` “Not yet measured” dumps harness copy (`ENSEMBLE_ENABLED=false`, AutoLab line). 404 on `/api/v1/ensemble/autolab` | `evidence/PC04_eval_autolab_dump.png` |
| PC05 | MED | Logged-out `/portfolio` hard-redirects to `/auth/login` with no `next=` return path | `evidence/PC05_portfolio_login_redirect.png` |
| PC06 | MED | Market `<title>` falls back to raw slug (`pm-will-spain-… \| AlphaEdge`) even when on-page h1 is human | `evidence/PC06_market_title_slug.png` (title measured in probe) |
| PC07 | LOW-MED | `/markets` empty filter copy is thin: “No markets in this filter.” | `evidence/PC03_markets_no_h1.png` (filter chrome) |
| PC08 | INFO | No theme toggle; light class does not retheme app chrome | `evidence/PC08_light_class_no_ui_theme.png` |
| PC09 | INFO | Leaderboard honest empty — no trader profiles to open | `evidence/PC07_leaderboard_empty_no_traders.png` |

### Not filed (intentional / not a defect)
- AlertsBell `9+` while logged out — public unread alert count vs last-seen (by design).
- Duplicate Portfolio nav + CTA — intentional primary action.
- Truncated long market titles in cards — expected ellipsis, not a glitch.

## U2 plan (top ~8)
Fix PC01–PC07 in `frontend/src` only; one commit per cluster. PC08/PC09 document-only (no invented theme system / fake traders).
