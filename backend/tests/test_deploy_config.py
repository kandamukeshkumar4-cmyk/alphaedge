from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_dockerfile_has_cloud_start_command():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "CMD" in dockerfile
    assert "alembic upgrade head" in dockerfile
    assert "uvicorn app.main:app" in dockerfile
    assert "${PORT:-8000}" in dockerfile


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


def test_public_frontend_does_not_default_to_localhost_api():
    for path in [
        ROOT / "frontend" / "src" / "app" / "admin" / "page.tsx",
        ROOT / "frontend" / "src" / "app" / "markets" / "page.tsx",
        ROOT / "frontend" / "src" / "app" / "eval" / "page.tsx",
    ]:
        source = path.read_text(encoding="utf-8")
        assert "localhost" not in source.lower()
