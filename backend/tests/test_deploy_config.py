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
    assert "az postgres flexible-server create" in script
    assert "az acr create" in script
    assert "az containerapp create" in script
    assert "min-replicas 0" in script
    assert "PAPER_TRADING_ONLY=true" in script
    assert "az consumption budget create" in script


def test_vercel_deploy_script_requires_public_api_url():
    script = (ROOT / "scripts" / "deploy_vercel.ps1").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_API_URL" in script
    assert "--build-env" in script
    assert "--prod" in script
    assert "localhost" not in script.lower()
