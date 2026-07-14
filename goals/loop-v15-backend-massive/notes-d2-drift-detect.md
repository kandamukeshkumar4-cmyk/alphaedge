# D2 — ForecastScore drift detection worker

- New `app/eval/forecast_drift.py`: rolling Brier + ECE over ForecastScore
  (read-only join with ForecastLog probabilities).
- New `workers/drift_detect.py` (ops_alerts pattern): JobRun + loop heartbeat.
- Migration `042_forecast_drift_snapshots` → table `forecast_drift_snapshots`.
- Config: `FORECAST_DRIFT_*` baseline/threshold/window (separate from U12).
- Minimal `tasks.py` append: function + 15-min cron. Alert publish is D3.
