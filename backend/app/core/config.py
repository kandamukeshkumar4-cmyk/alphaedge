from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import PAPER_TRADING_DISCLAIMER


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    paper_trading_only: bool = Field(default=True, alias="PAPER_TRADING_ONLY")
    database_url: str = Field(
        default="postgresql+asyncpg://alphaedge:alphaedge@localhost:5432/alphaedge",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql://alphaedge:alphaedge@localhost:5432/alphaedge",
        alias="DATABASE_URL_SYNC",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    admin_api_key: str = Field(default="dev-admin-key", alias="ADMIN_API_KEY")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    rate_limit: str = Field(default="60/minute", alias="RATE_LIMIT")
    system_account_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        alias="SYSTEM_ACCOUNT_ID",
    )
    smoke_account_id: str = Field(
        default="00000000-0000-0000-0000-000000000002",
        alias="SMOKE_ACCOUNT_ID",
    )
    system_initial_bankroll: float = Field(default=100_000.0, alias="SYSTEM_INITIAL_BANKROLL")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_reasoning_model: str = Field(default="gemini-2.5-pro", alias="GEMINI_REASONING_MODEL")
    gemini_judge_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_JUDGE_MODEL")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="alphaedge", alias="LANGSMITH_PROJECT")
    odds_api_key: str = Field(default="", alias="ODDS_API_KEY")
    odds_api_sport_keys: str = Field(default="basketball_nba", alias="ODDS_API_SPORT_KEYS")
    polymarket_market_slugs: str = Field(default="", alias="POLYMARKET_MARKET_SLUGS")
    kalshi_market_tickers: str = Field(default="", alias="KALSHI_MARKET_TICKERS")

    @field_validator("paper_trading_only")
    @classmethod
    def must_be_paper_only(cls, v: bool) -> bool:
        if not v:
            raise ValueError("PAPER_TRADING_ONLY must be true for simulated-funds operation.")
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def odds_api_sport_key_list(self) -> List[str]:
        return self._csv_list(self.odds_api_sport_keys)

    @property
    def polymarket_market_slug_list(self) -> List[str]:
        return self._csv_list(self.polymarket_market_slugs)

    @property
    def kalshi_market_ticker_list(self) -> List[str]:
        return self._csv_list(self.kalshi_market_tickers)

    @property
    def openapi_description(self) -> str:
        return (
            "**AlphaEdge** — paper-trading prediction market platform for NBA, "
            "broader sports, and election markets.\n\n"
            f"> {PAPER_TRADING_DISCLAIMER}\n\n"
            "LLM agents (Week 4+) can explain and adjust confidence but **cannot bypass RiskAgent**. "
            "Orders flow only through RiskService → validated OrderIntent → OrderBookService."
        )

    @staticmethod
    def _csv_list(value: str) -> List[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
