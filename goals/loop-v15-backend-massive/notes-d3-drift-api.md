# D3 — Drift API + in-app alert

- `GET /api/v1/eval/drift` — newest-first ForecastDriftSnapshot series.
- On `degraded`, `maybe_dispatch_drift_alert` uses AlertDispatchService
  (persisted Alert + `alerts` WS topic) with hourly-bucket dedupe key
  `forecast_drift:YYYY-MM-DDTHH` (E3 pattern). No external push.
- Worker summary includes `alerted` boolean.
