import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_github_workflows_opt_into_node24_action_runtime():
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    legacy_node20_actions = [
        "actions/checkout@v3",
        "actions/checkout@v4",
        "actions/setup-node@v4",
        "actions/setup-python@v5",
    ]

    assert workflow_paths
    for workflow_path in workflow_paths:
        workflow = workflow_path.read_text(encoding="utf-8")
        assert (
            'FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"' in workflow
        ), f"{workflow_path.name} must opt JavaScript actions into Node 24"
        for legacy_action in legacy_node20_actions:
            assert (
                legacy_action not in workflow
            ), f"{workflow_path.name} still uses {legacy_action}"
        if "actions/checkout@" in workflow:
            assert "actions/checkout@v6" in workflow
        if "actions/setup-node@" in workflow:
            assert "actions/setup-node@v6" in workflow
        if "actions/setup-python@" in workflow:
            assert "actions/setup-python@v6" in workflow


def test_backend_dockerfile_has_cloud_start_command():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "CMD" in dockerfile
    assert "alembic upgrade head" in dockerfile
    assert "uvicorn app.main:app" in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert "libgomp1" in dockerfile
    assert '-e ".[dev]"' not in dockerfile


def test_backend_dockerignore_excludes_local_artifacts():
    dockerignore = (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")

    assert ".venv/" in dockerignore
    assert "__pycache__/" in dockerignore
    assert "backend/" in dockerignore


def test_azure_student_script_uses_free_tier_or_12_month_services():
    script = (ROOT / "scripts" / "deploy_azure_student.ps1").read_text(encoding="utf-8")

    assert "Azure for Students" in script
    assert "Standard_B1ms" in script
    assert "postgres flexible-server create" in script
    assert "acr create" in script
    assert "containerapp create" in script
    assert "docker build" in script
    assert "docker push" in script
    assert "min-replicas 0" in script
    assert "PAPER_TRADING_ONLY=true" in script
    assert "consumption budget create" in script
    assert "--category cost" in script
    assert "Invoke-Az" in script
    assert "listOfAllowedLocations" in script
    assert " -o " not in script


def test_vercel_deploy_script_requires_public_api_url():
    script = (ROOT / "scripts" / "deploy_vercel.ps1").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_API_URL" in script
    assert "--build-env" in script
    assert "--prod" in script
    assert "localhost" not in script.lower()


def test_azure_app_service_fallback_uses_free_sku():
    script = (ROOT / "scripts" / "deploy_azure_app_service_student.ps1").read_text(
        encoding="utf-8"
    )

    assert "--sku F1" in script
    assert "webapp create" in script
    assert "SCM_DO_BUILD_DURING_DEPLOYMENT=true" in script
    assert "PAPER_TRADING_ONLY=true" in script
    assert "alembic upgrade head" in script


def test_azure_static_web_apps_frontend_config():
    next_config = (ROOT / "frontend" / "next.config.ts").read_text(encoding="utf-8")
    package_json = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "staticwebapp.config.json").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "deploy_azure_static_webapp.ps1").read_text(
        encoding="utf-8"
    )

    assert "output: \"export\"" in next_config
    assert "\"build:static\"" in package_json
    assert "\"navigationFallback\"" in config
    assert "--sku Free" in script
    assert "--app-location frontend" in script
    assert "--output-location out" in script


def test_azure_static_web_apps_managed_api_unblocks_public_demo():
    workflow = (
        ROOT / ".github" / "workflows" / "azure-static-web-apps-proud-meadow-01b42b810.yml"
    ).read_text(encoding="utf-8")
    api_function = (ROOT / "api" / "src" / "functions" / "alphaedge.js").read_text(
        encoding="utf-8"
    )
    api_package = (ROOT / "api" / "package.json").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "staticwebapp.config.json").read_text(encoding="utf-8")

    assert 'api_location: "api"' in workflow
    assert '"main": "src/functions/*.js"' in api_package
    assert 'route: "v1/markets"' in api_function
    assert 'route: "v1/eval/aggregates"' in api_function
    assert "Lakers vs Celtics" in api_function
    assert '"/api/*"' in config


def test_azure_static_web_apps_admin_proxy_is_viewer_token_gated():
    api_function = (ROOT / "api" / "src" / "functions" / "alphaedge.js").read_text(
        encoding="utf-8"
    )
    proxy = (ROOT / "api" / "src" / "admin-proxy.js").read_text(encoding="utf-8")

    assert 'route: "proof/agents/runs"' in api_function
    assert 'route: "proof/agents/runs/{runId}"' in api_function
    assert 'route: "proof/agents/run/{slug}"' in api_function
    assert "proxyAdminAgentRuns" in api_function
    assert "proxyAdminAgentRunDetail" in api_function
    assert "proxyAdminAgentRun" in api_function
    assert "ADMIN_VIEWER_TOKEN" in proxy
    assert "ADMIN_API_KEY" in proxy
    assert "ALPHAEDGE_BACKEND_API_URL" in proxy
    assert "X-Admin-API-Key" in proxy
    assert "x-alphaedge-admin-viewer-token" in proxy


def test_admin_dashboard_uses_proof_proxy_for_run_actions():
    admin_page = (
        ROOT / "frontend" / "src" / "app" / "admin" / "page.tsx"
    ).read_text(encoding="utf-8")
    client = (
        ROOT / "frontend" / "src" / "lib" / "admin-proof-api.ts"
    ).read_text(encoding="utf-8")

    assert "runAdminAgentProof" in admin_page
    assert "marketSlug" in admin_page
    assert "`/api/proof/agents/run/${encodeURIComponent(marketSlug)}`" in client
    assert "ADMIN_API_KEY" not in admin_page
    assert "X-Admin-API-Key" not in client


def test_public_frontend_does_not_default_to_localhost_api():
    for path in [
        ROOT / "frontend" / "src" / "app" / "admin" / "page.tsx",
        ROOT / "frontend" / "src" / "app" / "markets" / "page.tsx",
        ROOT / "frontend" / "src" / "app" / "eval" / "page.tsx",
    ]:
        source = path.read_text(encoding="utf-8")
        assert "localhost" not in source.lower()


def test_koyeb_neon_script_uses_free_web_service_and_neon_env():
    script = (ROOT / "scripts" / "deploy_koyeb_neon.ps1").read_text(encoding="utf-8")

    assert "KOYEB_TOKEN" in script
    assert "apps init" in script
    assert "services get" in script
    assert "services create" in script
    assert "--instance-type" in script
    assert "free" in script
    assert "--git-builder" in script
    assert "docker" in script
    assert "--git-workdir" in script
    assert "backend" in script
    assert "--git-docker-dockerfile" in script
    assert "Dockerfile" in script
    assert "--ports" in script
    assert "8000:http" in script
    assert "--routes" in script
    assert "/:8000" in script
    assert "PAPER_TRADING_ONLY=true" in script
    assert "DATABASE_URL=" in script
    assert "DATABASE_URL_SYNC=" in script
    assert "CORS_ORIGINS=" in script
    assert "https://proud-meadow-01b42b810.7.azurestaticapps.net" in script
    assert "ADMIN_API_KEY=change-me" not in script


def test_frontend_api_url_can_be_set_for_azure_static_web_apps():
    workflow = (
        ROOT / ".github" / "workflows" / "azure-static-web-apps-proud-meadow-01b42b810.yml"
    ).read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "set_frontend_api_url.ps1").read_text(encoding="utf-8")

    assert "workflow_dispatch" in workflow
    assert "api_url:" in workflow
    assert "NEXT_PUBLIC_API_URL: ${{ inputs.api_url || secrets.NEXT_PUBLIC_API_URL }}" in workflow
    assert "gh secret set NEXT_PUBLIC_API_URL" in script
    assert "gh workflow run" in script
    assert "--field api_url=$ApiUrl" in script
    assert "azure-static-web-apps-proud-meadow-01b42b810.yml" in script


def test_koyebignore_limits_backend_redeploy_noise():
    koyebignore = (ROOT / ".koyebignore").read_text(encoding="utf-8")

    assert "frontend/" in koyebignore
    assert "docs/" in koyebignore
    assert "scripts/" in koyebignore
    assert ".github/" in koyebignore


def test_koyeb_neon_deploy_doc_exists():
    doc = (ROOT / "docs" / "deploy" / "KOYEB_NEON.md").read_text(encoding="utf-8")

    assert "Koyeb Free Web Service + Neon Free Postgres" in doc
    assert "PAPER_TRADING_ONLY=true" in doc
    assert "DATABASE_URL" in doc
    assert "DATABASE_URL_SYNC" in doc
    assert "NEXT_PUBLIC_API_URL" in doc
    assert "https://proud-meadow-01b42b810.7.azurestaticapps.net" in doc
    assert "/health" in doc


def test_huggingface_neon_deploy_doc_exists():
    doc = (ROOT / "docs" / "deploy" / "HUGGINGFACE_NEON.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Hugging Face Spaces + Neon Postgres" in doc
    assert "mukeshkumarkanda-alphaedge-api.hf.space" in doc
    assert "PAPER_TRADING_ONLY=true" in doc
    assert "DATABASE_URL" in doc
    assert "DATABASE_URL_SYNC" in doc
    assert "NEXT_PUBLIC_API_URL" in doc
    assert "https://proud-meadow-01b42b810.7.azurestaticapps.net" in doc
    assert "/health" in doc
    assert "set_hf_space_secrets.ps1" in doc
    assert "-ReplaceHfToken" in doc
    assert "HUGGINGFACE_NEON.md" in readme


def test_huggingface_space_dockerfile_is_self_contained():
    dockerfile = (ROOT / "backend" / "Dockerfile.hfspace").read_text(
        encoding="utf-8"
    )

    assert "COPY . ." in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert "--port 7860" in dockerfile
    assert "PAPER_TRADING_ONLY=true" in dockerfile
    assert "libgomp1" in dockerfile
    assert "git clone" not in dockerfile
    assert "git checkout" not in dockerfile
    assert "${PORT" not in dockerfile


def test_huggingface_space_workflow_deploys_backend_and_fails_without_proof():
    workflow = (ROOT / ".github" / "workflows" / "deploy-hf-space.yml").read_text(
        encoding="utf-8"
    )

    assert 'paths: ["backend/**"]' in workflow
    assert "HF_TOKEN: ${{ secrets.HF_TOKEN }}" in workflow
    assert "NEON_DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}" in workflow
    assert "NEON_DATABASE_URL_SYNC: ${{ secrets.NEON_DATABASE_URL_SYNC }}" in workflow
    assert "ADMIN_API_KEY: ${{ secrets.ADMIN_API_KEY }}" in workflow
    assert "HF_TOKEN GitHub Actions secret is required" in workflow
    assert "NEON_DATABASE_URL GitHub Actions secret is required" in workflow
    assert "ADMIN_API_KEY GitHub Actions secret is required" in workflow
    assert "sync_runtime_secrets:" in workflow
    assert "Sync GitHub Actions secrets into the HF Space before deploying" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.sync_runtime_secrets" in workflow
    assert "Skipping HF Space runtime secret sync" in workflow
    assert "api.add_space_secret" in workflow
    assert "HfHubHTTPError" in workflow
    assert "add_space_secret_with_retry" in workflow
    assert "Retrying HF Space secret sync after 429" in workflow
    assert "secret_sync_deadline = time.monotonic() + 600" in workflow
    assert "attempt = 1" in workflow
    assert "time.monotonic() >= secret_sync_deadline" in workflow
    assert "attempt += 1" in workflow
    assert "for attempt in range(1, 6)" not in workflow
    assert "api.add_space_variable" not in workflow
    assert "DATABASE_URL_SYNC" in workflow
    assert "cp -r backend/. hf_stage/" in workflow
    assert "cp hf_stage/Dockerfile.hfspace hf_stage/Dockerfile" in workflow
    assert "app_port: 7860" in workflow
    assert "id: push_space" in workflow
    assert "git push" in workflow
    assert "space_sha=$(git rev-parse HEAD)" in workflow
    assert 'echo "space_sha=$space_sha" >> "$GITHUB_OUTPUT"' in workflow
    assert "steps.push_space.outputs.space_sha" in workflow
    assert "https://huggingface.co/api/spaces/mukeshkumarkanda/alphaedge-api/runtime" in workflow
    assert "runtime.get(\"sha\")" in workflow
    assert "Space runtime is running the pushed revision" in workflow
    assert "Expected paper_trading_only=true from /health" in workflow
    assert "Canonical Lakers vs Celtics market was not returned" in workflow
    assert "Canonical market lock_at must be in the future for browser paper trading" in workflow
    assert "Los Angeles mayoral election market was not returned" in workflow
    assert "Expected Politics category on election market" in workflow
    assert "/api/v1/markets/elect-la-mayor-2026/snapshot" in workflow
    assert "Expected snapshot route to return the election market" in workflow
    assert "Waiting for markets endpoint to return canonical market" in workflow
    assert "Smoke-test admin agent proof endpoint" in workflow
    assert "/admin/agents/run/nba-2025-01-15-lal-bos" in workflow
    assert "X-Admin-API-Key: ${ADMIN_API_KEY}" in workflow
    assert "Expected agent proof for canonical Lakers vs Celtics market" in workflow
    assert "Expected paper-trading simulation disclaimer from agent proof" in workflow
    assert "Expected risk step in deployed agent proof" in workflow
    assert "Deployed agent proof unexpectedly created execution artifacts" in workflow
    assert "Smoke-test paper order lifecycle" in workflow
    assert "/api/v1/paper-account" in workflow
    assert "/admin/smoke-account" in workflow
    assert 'MARKET_SLUG = "nba-2025-01-15-lal-bos"' in workflow
    assert 'f"/api/v1/markets/{MARKET_SLUG}/orders"' in workflow
    assert 'f"/api/v1/orders/{order_id}/cancel"' in workflow
    assert "Expected paper account endpoint to report paper_trading_only=true" in workflow
    assert "Expected admin smoke account endpoint to report paper_trading_only=true" in workflow
    assert "Expected risk-gated paper order to open" in workflow
    assert "Expected cancellation to release smoke-test order" in workflow
    assert "Smoke paper order leaked into the public paper account" in workflow
    assert "Smoke paper order was not removed from smoke-account open orders" in workflow
    assert "Attempt $i/40: /api/v1/markets HTTP $status" in workflow
    assert "ERROR: /api/v1/markets did not return the canonical market in time." in workflow
    assert "ERROR: health check timed out" in workflow
    assert "WARNING: health check timed out" not in workflow
    assert "WARNING: /api/v1/markets" not in workflow


def test_market_catalog_metadata_uses_incremental_migration():
    initial = (ROOT / "backend" / "alembic" / "versions" / "001_initial_schema.py").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT / "backend" / "alembic" / "versions" / "002_market_catalog_metadata.py"
    ).read_text(encoding="utf-8")
    initial_markets_table = initial.split('op.create_table(\n        "markets",', 1)[1].split(
        'op.create_index("ix_markets_slug"',
        1,
    )[0]

    catalog_columns = [
        "category",
        "icon",
        "volume",
        "traders",
        "market_count",
        "description",
        "resolution",
    ]
    for column in catalog_columns:
        assert f'"{column}"' not in initial_markets_table
        assert re.search(
            rf'op\.add_column\(\s*"markets",\s*sa\.Column\("{column}"',
            migration,
        )

    assert 'down_revision: Union[str, None] = "001"' in migration


def test_huggingface_neon_doc_uses_automated_deploy_not_sha_pinning():
    doc = (ROOT / "docs" / "deploy" / "HUGGINGFACE_NEON.md").read_text(
        encoding="utf-8"
    )

    assert ".github/workflows/deploy-hf-space.yml" in doc
    assert "HF_TOKEN" in doc
    assert "NEON_DATABASE_URL" in doc
    assert "sync_runtime_secrets=true" in doc
    assert "Routine push deploys do not rewrite HF Space secrets" in doc
    assert "Dockerfile.hfspace" in doc
    assert "pushed Space revision" in doc
    assert "git checkout" not in doc
    assert "update the pinned" not in doc.lower()


def test_huggingface_paper_trading_ready_script_checks_live_order_lifecycle():
    script = (ROOT / "scripts" / "verify_hf_paper_trading_ready.ps1").read_text(
        encoding="utf-8"
    )

    assert "https://mukeshkumarkanda-alphaedge-api.hf.space" in script
    assert "https://proud-meadow-01b42b810.7.azurestaticapps.net" in script
    assert "nba-2025-01-15-lal-bos" in script
    assert "elect-la-mayor-2026" in script
    assert "$ApiUrl/health" in script
    assert "$ApiUrl/api/v1/markets" in script
    assert "$ApiUrl/api/v1/markets/$ElectionSlug/snapshot" in script
    assert "$ApiUrl/api/v1/paper-account" in script
    assert "$ApiUrl/admin/smoke-account" in script
    assert "$ApiUrl/api/v1/markets/$MarketSlug/orders" in script
    assert "$ApiUrl/api/v1/orders/$orderId/cancel" in script
    assert "paper_trading_only" in script
    assert "MaxAttempts = 40" in script
    assert "RetryDelaySec = 15" in script
    assert "Invoke-JsonWithRetry" in script
    assert "Expand-JsonArray" in script
    assert "Attempt $attempt/${MaxAttempts}" in script
    assert "Expected risk-gated paper order to open" in script
    assert "lock_at must be in the future for browser paper trading" in script
    assert "Smoke paper order was not removed from open orders after cancel" in script
    assert "Smoke paper order leaked into the public paper account" in script
    assert "X-Admin-API-Key" in script
    assert "SkipAdminProof" in script
    assert "Expected deployed risk step to reject weak edge" in script
    assert "Deployed agent proof unexpectedly created execution artifacts" in script
    assert "Frontend markets bundle is not pointed at" in script


def test_huggingface_neon_doc_and_readme_link_live_verifier():
    doc = (ROOT / "docs" / "deploy" / "HUGGINGFACE_NEON.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "scripts/verify_hf_paper_trading_ready.ps1" in doc
    assert "scripts/verify_hf_paper_trading_ready.ps1" in readme
    assert "paper order lifecycle" in doc
    assert "admin agent proof" in doc


def test_huggingface_space_secret_bootstrap_script_sets_required_github_secrets():
    script = (ROOT / "scripts" / "set_hf_space_secrets.ps1").read_text(
        encoding="utf-8"
    )

    assert "gh secret set $Name --repo $Repo" in script
    assert 'Set-GitHubSecret "HF_TOKEN" $HfToken -Required' in script
    assert "-ReplaceExisting:$ReplaceHfToken" in script
    assert "ReplaceHfToken" in script
    assert 'Set-GitHubSecret "NEON_DATABASE_URL" $NeonDatabaseUrl -Required' in script
    assert 'Set-GitHubSecret "ADMIN_API_KEY" $AdminApiKey -Required' in script
    assert 'Set-GitHubSecret "NEON_DATABASE_URL_SYNC" $NeonDatabaseUrlSync -Required' in script
    assert "gh secret list --repo $Repo" in script
    assert "already exists on $Repo; leaving it unchanged" in script
    assert "Paste $Name when prompted by GitHub CLI" in script
    assert "deploy-hf-space.yml" in script
    assert "gh workflow run" in script
    assert "--field sync_runtime_secrets=true" in script
    assert "-TriggerDeploy" in script
    assert "hf_xxx" not in script


def test_koyeb_backend_github_workflow_is_manual_and_secret_driven():
    workflow = (ROOT / ".github" / "workflows" / "deploy-koyeb-backend.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch" in workflow
    assert "KOYEB_TOKEN: ${{ secrets.KOYEB_TOKEN }}" in workflow
    assert "NEON_DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}" in workflow
    assert "NEON_DATABASE_URL_SYNC: ${{ secrets.NEON_DATABASE_URL_SYNC }}" in workflow
    assert "ADMIN_API_KEY: ${{ secrets.ADMIN_API_KEY }}" in workflow
    assert "deploy_koyeb_neon.ps1" in workflow
    assert "koyeb-cli/master/install.sh" in workflow
    assert "curl --fail" in workflow
    assert "retry $i/20" in workflow
    assert "/health" in workflow
    assert "actions: write" in workflow
    assert "gh workflow run azure-static-web-apps-proud-meadow-01b42b810.yml" in workflow
    assert "--field api_url=${{ inputs.api_url }}" in workflow


def test_koyeb_neon_secret_bootstrap_script_sets_required_github_secrets():
    script = (ROOT / "scripts" / "set_koyeb_neon_secrets.ps1").read_text(
        encoding="utf-8"
    )

    assert "gh secret set KOYEB_TOKEN" in script
    assert "gh secret set NEON_DATABASE_URL" in script
    assert "gh secret set ADMIN_API_KEY" in script
    assert "gh secret set NEON_DATABASE_URL_SYNC" in script
    assert "deploy-koyeb-backend.yml" in script
    assert "gh workflow run" in script
    assert "-TriggerDeploy" in script
    assert "https://alphaedge-api.koyeb.app" in script
    assert "change-me" not in script


def test_koyeb_neon_readiness_script_checks_backend_and_frontend():
    script = (ROOT / "scripts" / "verify_koyeb_neon_ready.ps1").read_text(
        encoding="utf-8"
    )
    doc = (ROOT / "docs" / "deploy" / "KOYEB_NEON.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "KOYEB_TOKEN" in script
    assert "NEON_DATABASE_URL" in script
    assert "ADMIN_API_KEY" in script
    assert "$ApiUrl/health" in script
    assert "$ApiUrl/api/v1/markets" in script
    assert "nba-2025-01-15-lal-bos" in script
    assert "No active service" in script
    assert "Frontend markets bundle is not pointed at" in script
    assert "verify_koyeb_neon_ready.ps1" in doc
    assert "verify_koyeb_neon_ready.ps1" in readme
