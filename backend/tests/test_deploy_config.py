from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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
    assert "HUGGINGFACE_NEON.md" in readme


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
