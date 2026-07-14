# AlphaEdge frontend

Next.js UI for the paper-trading prediction-market simulation.

> **Simulated funds only.** Pair with a backend that has
> `PAPER_TRADING_ONLY=true`.

## Quick commands

```bash
# From frontend/
npm install
# optional: NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.local
npm run dev

npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e   # Playwright
```

## Deploy

Vercel project root: `frontend/`. Set `NEXT_PUBLIC_API_URL` to the public API
origin. See [docs/operations.md](../docs/operations.md).

## Docs

- [User guide](../docs/user-guide.md)
- [API reference](../docs/api.md)
- Root [README](../README.md)
