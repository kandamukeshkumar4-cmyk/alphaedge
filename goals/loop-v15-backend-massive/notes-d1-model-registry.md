# D1 — Model registry completed

- Finished existing `ml/versioning.py` (did not rebuild classifier factory).
- Migration `041_model_registry_active`: `training_data_hash`, `is_active` on
  `model_versions` + singleton `model_active_pointer` (active + previous).
- Admin `GET /api/v1/models`, `POST …/{id}/activate`, `POST …/rollback`.
- Registration requires `training_data_hash`; metrics normalize `brier` /
  `calibration` / `expected_calibration_error`. Activation is never default.
