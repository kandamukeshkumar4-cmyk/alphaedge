# D4 — Scheduled retrain (flag-gated, default OFF)

- `ML_RETRAIN_ENABLED` default false; `ML_RETRAIN_MIN_ROWS` default 20.
- `workers/model_retrain.py`: load resolved-snapshot matrix → train XGBoost →
  register via D1 with `activate=False` → log activation recommendation.
- Never auto-activates. Daily cron 04:00 (no-op while flag off).
- `train_xgboost_from_feature_matrix` extracted for snapshot-store training.
