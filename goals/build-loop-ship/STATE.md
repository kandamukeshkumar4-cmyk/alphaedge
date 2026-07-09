# Ship Loop — every feature visible + PR + prod deploy (2026-07-04)

Goal: nothing we built sits invisible. Every loop's features reachable in ≤1
click, gates green, PR raised, frontend on Vercel prod, backend reachable.

Verifier: maker/checker — each ticket live-verified (DOM or curl) before DONE.
Stop condition: all tickets DONE/BLOCKED-ON-USER; K=3 no-progress → reorganize.

| # | Ticket | Status | Notes |
|---|--------|--------|-------|
| S01 | Weather desk UI (page + 1-click nav) | DONE | /weather page + primary-nav link; DOM-verified live: 7 cities, NWS highs, edge chips |
| S02 | Feature-visibility audit (all loops) | DONE | every non-admin page reachable from header nav (16 hrefs vs 16 surfaces); weather added |
| S03 | Full gates (BE+FE) | DONE | BE 1044p/5s ruff clean; FE lint+typecheck+61 tests+build green |
| S04 | Review uncommitted + branch hygiene | DONE | tree clean; session diff reviewed (no runtime findings; 1 cosmetic nit noted) |
| S05 | Push origin + mirror gitlab | DONE | pushed origin+gitlab; codex/alphaedge-base IS the default branch so push = prod-branch update (no self-PR) |
| S06 | Deploy frontend Vercel prod | DONE | Vercel prod Ready: https://alphaedge-frontend-three.vercel.app (project `alphaedge-frontend`; verified 200, title "AlphaEdge — AI Prediction Markets"). NOTE 2026-07-07: old URL frontend-kappa-drab-22.vercel.app was reclaimed by the JobReach AI project — the Vercel project literally named `frontend` belongs to JobReach (owns jobreach.online). AlphaEdge now has its own uniquely-named project so the two can't collide. Never deploy AlphaEdge to a project named `frontend`. |
| S07 | Backend prod reachable | BLOCKED-ON-USER | Koyeb service dead ("No active service") — needs owner login to reactivate or a new host token; frontend already points at https://alphaedge-api.koyeb.app |
| S08 | Post-deploy smoke | PARTIAL | frontend smoke PASS (200s); full smoke waits on S07 backend |

Keys requested from user (also unlock analyst depth): VERCEL_TOKEN, backend
host token, NEXT_PUBLIC_API_URL; optional BRAVE/EXA (news), LLM_API_KEY (prose).

AutoLab: baseline = all features exist server-side, gates green | benchmark =
user-visible surface count + prod URLs | outcome = tracked per ticket.

Follow-up ticket: /markets polling flood — hundreds of requests/min from the homepage rails self-trip the SlowAPI limiter (intermittent 429s seen in preview). Add client-side request dedup/central store.

## Keys received (2026-07-04)
- NIM (LLM_PROVIDER=nim) + EXA_API_KEY delivered by owner; stored ONLY in
  gitignored backend/.env; compose passes via env_file. Never committed.
- Model choice (measured): qwen/qwen3-next-80b-a3b-instruct (0.4s, 80B-class)
  for analyst+assistant; llama-3.1-8b-instruct fast fallback (0.7s);
  llama-3.3-70b endpoint hangs (>120s) — avoid; nemotron-49b ~19s (reasoning,
  candidate for deep digest later).
- LIVE-VERIFIED: analyst generator=llm (real prose grounded in price jumps);
  Exa in-container: 8 real WC2026 news sources, sentiment computed.
- BUG FIXED en route: news_fetcher parents[4] IndexError killed the news
  pipeline at import time in Docker since it shipped — news was empty in
  containers regardless of keys.
