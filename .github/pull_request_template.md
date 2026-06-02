## Claim

Gate claimed:
- [ ] Week 1 CLOB/API
- [ ] Week 2 backtest/ML
- [ ] Week 3 eval/risk
- [ ] Week 4 agents/dashboard
- [ ] Week 5 deploy

## Summary

- 

## Verification

- [ ] `uv run --extra dev pytest -q`
- [ ] `uv run --extra dev ruff check app tests`
- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] `docker compose up --build` and `/health` checked, if Docker is available

## Risk

- Paper-trading only: simulated funds only, with no cash funding or external execution paths.
- Agent safety: raw LLM text cannot bypass `RiskService`.
