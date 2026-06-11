import pytest
from pydantic import ValidationError

from app.core.config import Settings



def test_production_requires_non_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(APP_ENV="production", JWT_SECRET_KEY="dev-jwt-secret-change-in-production")


def test_local_development_allows_default_jwt_secret():
    settings = Settings(APP_ENV="development")

    assert settings.jwt_secret_key == "dev-jwt-secret-change-in-production"


def test_market_adapter_settings_have_safe_defaults():
    settings = Settings(APP_ENV="development")

    assert settings.polymarket_gamma_base_url == "https://gamma-api.polymarket.com"
    assert settings.kalshi_api_base_url == "https://external-api.kalshi.com/trade-api/v2"
    assert settings.kalshi_api_key_id == ""
    assert settings.kalshi_private_key_pem == ""


def test_paper_trading_only_cannot_be_disabled():
    with pytest.raises(ValidationError, match="PAPER_TRADING_ONLY"):
        Settings(PAPER_TRADING_ONLY=False)
