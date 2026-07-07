# Hugging Face Spaces + Neon Postgres

This is the current no-card backend unblock for AlphaEdge.

Frontend stays on Azure Static Web Apps:

```text
https://proud-meadow-01b42b810.7.azurestaticapps.net
```

Backend runs on a public Hugging Face Docker Space:

```text
https://mukeshkumar007-alphaedge-api.hf.space
```

Database runs on Neon Postgres.

## Current status

The Koyeb path remains documented in `docs/deploy/KOYEB_NEON.md`, but the
account setup flow required payment verification before deploying a service.
For the free/no-card portfolio demo path, use Hugging Face Spaces instead.

## Runtime secrets

Set these as GitHub Actions secrets, not repository files:

```text
HF_TOKEN=<huggingface write token for mukeshkumar007>
NEON_DATABASE_URL=<neon SQLAlchemy URL>
NEON_DATABASE_URL_SYNC=<optional neon sync SQLAlchemy URL>
ADMIN_API_KEY=<long random secret>
```

The deploy workflow can sync those GitHub secrets into the Hugging Face Space
during a manual/bootstrap run as:

```text
DATABASE_URL
DATABASE_URL_SYNC
ADMIN_API_KEY
```

If `NEON_DATABASE_URL_SYNC` is omitted, the workflow derives it from
`NEON_DATABASE_URL`. Routine push deploys do not rewrite HF Space secrets; this
avoids Hugging Face API rate limits. Use the manual `sync_runtime_secrets=true`
input after first setup or secret rotation.

The Space Dockerfile sets these non-secret runtime defaults:

```text
PAPER_TRADING_ONLY=true
CORS_ORIGINS=https://proud-meadow-01b42b810.7.azurestaticapps.net
REDIS_URL=redis://disabled:6379/0
```

## Space Dockerfile

The HF-specific Dockerfile lives at `backend/Dockerfile.hfspace`. It copies
code directly (no GitHub clone, no pinned SHA) and exposes port `7860`:

```dockerfile
# see backend/Dockerfile.hfspace
EXPOSE 7860
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 7860"]
```

## Automated deploy

The workflow `.github/workflows/deploy-hf-space.yml` triggers automatically on
any push to `codex/alphaedge-base` that touches `backend/**`. It:

1. Stages `backend/` as the Space root.
2. Renames `Dockerfile.hfspace` to `Dockerfile`.
3. Git-pushes to `https://huggingface.co/spaces/mukeshkumar007/alphaedge-api`.
4. Waits for Hugging Face runtime metadata to report the pushed Space revision
   as `RUNNING`.
5. Waits up to 10 min for `/health` to return 200 with `paper_trading_only=true`.
6. Smoke-tests `/api/v1/markets`, election market snapshots, admin agent proof,
   and the paper order lifecycle.

Manual runs can also sync GitHub Actions secrets and runtime variables to the
HF Space before deploying when `sync_runtime_secrets=true`.

The workflow fails if the pushed Space revision does not become the running
runtime, or if either runtime proof step fails.

To set the required GitHub secrets from this machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_hf_space_secrets.ps1
```

From outside the repo, use the absolute path:

```powershell
powershell -ExecutionPolicy Bypass -File "E:\polymarket clone\scripts\set_hf_space_secrets.ps1"
```

The script prompts for `HF_TOKEN`, `NEON_DATABASE_URL`, and `ADMIN_API_KEY`
through GitHub CLI when they are missing, so secret values do not need to
appear in the command line. Existing secrets are left unchanged unless you pass
replacement values.
If `HF_TOKEN` was created empty or needs to be rotated, rerun:

```powershell
powershell -ExecutionPolicy Bypass -File "E:\polymarket clone\scripts\set_hf_space_secrets.ps1" -ReplaceHfToken
```

Use `-SetNeonDatabaseUrlSync` only if you want to provide a separate
`NEON_DATABASE_URL_SYNC`; otherwise the workflow derives it.

You can also add the secrets manually at:
`Settings -> Secrets and variables -> Actions -> New repository secret`.

First-time order:

1. Run `scripts/set_hf_space_secrets.ps1` to create the GitHub secrets.
2. Trigger the workflow once with `sync_runtime_secrets=true` to write the
   runtime secrets into the HF Space.
3. Commit and push repo changes. Backend pushes trigger deploys automatically
   if they include `backend/**`.

To set GitHub secrets and immediately trigger the bootstrap sync deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_hf_space_secrets.ps1 -TriggerDeploy
```

To trigger a manual redeploy without a code change:

```bash
gh workflow run deploy-hf-space.yml
```

To manually resync rotated runtime secrets before redeploying:

```bash
gh workflow run deploy-hf-space.yml --field sync_runtime_secrets=true
```

The workflow must exist on the remote branch before GitHub can run it.

## Verify backend

Run the reusable live verifier after deploys, frontend URL switches, or secret
rotation:

```powershell
powershell -ExecutionPolicy Bypass -File ./scripts/verify_hf_paper_trading_ready.ps1
```

If you are running a public check without the admin secret, skip only the
protected admin agent proof:

```powershell
powershell -ExecutionPolicy Bypass -File ./scripts/verify_hf_paper_trading_ready.ps1 -SkipAdminProof
```

The script checks health, canonical NBA and election markets, the election
snapshot, the Azure frontend bundle, one risk-gated paper order lifecycle, and
admin agent proof when `ADMIN_API_KEY` or `-AdminApiKey` is supplied.

```powershell
Invoke-RestMethod https://mukeshkumar007-alphaedge-api.hf.space/health
Invoke-RestMethod https://mukeshkumar007-alphaedge-api.hf.space/api/v1/markets
```

Expected:

```text
status=ok
paper_trading_only=true
Lakers vs Celtics market is returned
```

## Point frontend at the Space

Use the existing helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_frontend_api_url.ps1 `
  -ApiUrl "https://mukeshkumar007-alphaedge-api.hf.space"
```

This sets:

```text
NEXT_PUBLIC_API_URL=https://mukeshkumar007-alphaedge-api.hf.space
```

Then it triggers the Azure Static Web Apps workflow with the same `api_url`
workflow input so the static Next.js export bakes in the backend URL.

## Verify frontend

```powershell
Invoke-WebRequest https://proud-meadow-01b42b810.7.azurestaticapps.net/markets
```

The page should show:

```text
Lakers vs Celtics - nba-2025-01-15-lal-bos (open)
```

## Limitations

- Hugging Face free CPU Spaces can sleep or cold start.
- This deploy runs the API only; no worker is attached to `REDIS_URL`.
- Keep the Space public for the portfolio demo unless you add an auth layer.
- The live paper-order smoke test uses the admin-only deployment smoke account
  so deploy verification does not add cancelled orders to the public portfolio.
- This remains paper-trading only with simulated funds and no external execution paths.
