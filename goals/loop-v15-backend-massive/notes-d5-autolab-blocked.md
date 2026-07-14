# D5 — AutoLab calibration pass

## Verdict

**blocked on resolved-count — honest skip**

## Evidence (read-only)

- `GET https://mukeshkumar007-alphaedge-api.hf.space/api/v1/system/resolved-count`
  → HTTP 503, body: `Your space is in error, check its status on hf.co`
- Alternate Koyeb URL also unavailable (404 no active service).

Cannot honestly claim ≥100 resolved outcomes. No calibration edits, no
post-close training, no metric gaming.

```text
AutoLab: baseline=n/a | benchmark=resolved-count≥100 | iterations=0 | budget=0/1 | outcome=retired (blocked on resolved-count)
```
