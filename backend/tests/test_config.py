import pytest
from pydantic import ValidationError

from app.core.config import Settings



def test_production_requires_non_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(APP_ENV="production", JWT_SECRET_KEY="dev-jwt-secret-change-in-production")


def test_production_requires_non_default_admin_api_key():
    # ADMIN_API_KEY pinned to the shipped default: local .env may override it.
    with pytest.raises(ValidationError, match="ADMIN_API_KEY"):
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="explicit-prod-secret",
            ADMIN_API_KEY="dev-admin-key",
        )


def test_production_accepts_explicit_secrets():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="explicit-prod-secret",
        ADMIN_API_KEY="explicit-prod-admin-key",
    )

    assert settings.admin_api_key == "explicit-prod-admin-key"


def test_local_development_allows_default_jwt_secret():
    settings = Settings(APP_ENV="development")

    assert settings.jwt_secret_key == "dev-jwt-secret-change-in-production"


def test_market_adapter_settings_have_safe_defaults():
    settings = Settings(APP_ENV="development")

    assert settings.polymarket_gamma_base_url == "https://gamma-api.polymarket.com"
    assert settings.kalshi_api_base_url == "https://api.elections.kalshi.com/trade-api/v2"
    assert settings.kalshi_api_key_id == ""
    assert settings.kalshi_signing_pem == ""


def test_paper_trading_only_cannot_be_disabled():
    with pytest.raises(ValidationError, match="PAPER_TRADING_ONLY"):
        Settings(PAPER_TRADING_ONLY=False)
