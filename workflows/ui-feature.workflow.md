# Workflow: ui-feature

For any `extension/` or `frontend/` change.

## Steps

1. **Start green.** Run the relevant verify set below and confirm it passes before editing. Branch off `codex/alphaedge-base`.
2. **Read the contract.** Open the goal file in `/goals`, its `docs/project/QUANT_ROADMAP.md` phase, and the listed components/files.
3. **Implement the smallest slice.** Reuse existing pieces — `extension/src/platforms.ts` (URL parsers), `extension/src/backend-client.ts`, the overlay host, and the existing `frontend/src/app` surfaces. Call backend endpoints; do not recompute signal math client-side.
4. **Honest labels (required):** every signal/prediction surface shows sample size / provisional state and a persistent "Research / not financial advice — verify resolution terms" label. Models failing the CLV gate must NOT render as "edge."
5. **Verify (required):**
   - Extension: `cd extension && npm test && npm run typecheck && npm run build`
   - Frontend: `cd frontend && npm run lint && npm run typecheck && npm run build`
6. **Safety check:** minimal host permissions (Polymarket, Kalshi, FanDuel, AlphaEdge API only); no odds scraping on Polymarket/Kalshi (server-side adapters only); FanDuel manual-only; no wallet/key/account-scraping code. The manifest-safety + no-scraping tests must pass.
7. **Review gate:** `requesting-code-review` (or manual-diff fallback); `bumblebee-supply-chain-scan` if `package.json`/lockfile changed.
8. **Hand off:** update `/goals/README.md` status; record the PR line.

## Done when
Verify sets are green, honest labels present, safety/permission tests pass, review gate satisfied, status + PR line recorded.
