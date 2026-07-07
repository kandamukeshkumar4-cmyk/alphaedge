from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
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
    app_env: str = Field(default="development", alias="APP_ENV")
    admin_api_key: str = Field(default="dev-admin-key", alias="ADMIN_API_KEY")
    jwt_secret_key: str = Field(default="dev-jwt-secret-change-in-production", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, alias="JWT_EXPIRE_MINUTES")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    rate_limit: str = Field(default="600/minute", alias="RATE_LIMIT")
    live_feed_enabled: bool = Field(default=True, alias="LIVE_FEED_ENABLED")
    live_tick_interval_sec: int = Field(default=15, alias="LIVE_TICK_INTERVAL_SEC")
    live_ingest_interval_sec: int = Field(default=1800, alias="LIVE_INGEST_INTERVAL_SEC")
    live_ingest_total_limit: int = Field(default=100, alias="LIVE_INGEST_TOTAL_LIMIT")
    live_ingest_min_volume_24h: float = Field(
        default=10_000.0, alias="LIVE_INGEST_MIN_VOLUME_24H"
    )
    # In-process scheduler flags — the deployed free tier has no ARQ worker
    # (REDIS_URL=redis://disabled), so the periodic worker tasks must run
    # in-process inside the API. Each defaults to True; set to False to opt
    # out of an individual loop without touching the others.
    scheduler_news_scan_enabled: bool = Field(
        default=True, alias="SCHEDULER_NEWS_SCAN_ENABLED"
    )
    scheduler_weather_scan_enabled: bool = Field(
        default=True, alias="SCHEDULER_WEATHER_SCAN_ENABLED"
    )
    scheduler_morning_research_enabled: bool = Field(
        default=True, alias="SCHEDULER_MORNING_RESEARCH_ENABLED"
    )
    scheduler_whale_refresh_enabled: bool = Field(
        default=True, alias="SCHEDULER_WHALE_REFRESH_ENABLED"
    )
    scheduler_wc2026_resolve_enabled: bool = Field(
        default=True, alias="SCHEDULER_WC2026_RESOLVE_ENABLED"
    )
    # Per-IP rate limit for the anonymous (no-token) assistant chat path.
    # Authenticated requests bypass this; anon demo traffic is bounded.
    assistant_anon_rate_per_min: int = Field(
        default=10, alias="ASSISTANT_ANON_RATE_PER_MIN"
    )
    system_account_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        alias="SYSTEM_ACCOUNT_ID",
    )
    smoke_account_id: str = Field(
        default="00000000-0000-0000-0000-000000000002",
        alias="SMOKE_ACCOUNT_ID",
    )
    system_initial_bankroll: float = Field(default=100_000.0, alias="SYSTEM_INITIAL_BANKROLL")

    # News signals (last30days skill)
    news_signals_enabled: bool = Field(default=True, alias="NEWS_SIGNALS_ENABLED")
    news_signals_timeout: float = Field(default=25.0, alias="NEWS_SIGNALS_TIMEOUT")
    # Optional API keys forwarded to last30days.py (all have free-tier fallbacks)
    scrapecreators_api_key: str = Field(default="", alias="SCRAPECREATORS_API_KEY")
    brave_api_key: str = Field(default="", alias="BRAVE_API_KEY")
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_reasoning_model: str = Field(default="gemini-2.5-pro", alias="GEMINI_REASONING_MODEL")
    gemini_judge_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_JUDGE_MODEL")

    # LLM provider (OpenAI-compatible: OpenAI, NVIDIA NIM, Gemini)
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    # Reasoning model for deep, latency-tolerant work (the daily digest). Empty
    # falls back to LLM_MODEL, so per-feature routing is opt-in.
    llm_model_deep: str = Field(default="", alias="LLM_MODEL_DEEP")
    nim_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        alias="NIM_BASE_URL",
    )
    nim_api_key: str = Field(default="", alias="NIM_API_KEY")

    # --- Per-use-case model routing ---
    # Two modes:
    #   1. NIM-native (recommended): one NIM_API_KEY, different NIM-hosted models
    #      per use case via LLM_MODEL_CHAT, LLM_MODEL_ANALYST, etc.
    #   2. Multi-provider: separate API keys for DeepSeek/Kimi/GLM via
    #      LLM_ROUTE_* + provider-specific keys (for users with direct accounts).
    #
    # When a per-use-case model is set AND we're on NIM, that model is used with
    # the NIM endpoint. When a LLM_ROUTE_* points to a separate provider with a
    # key, that provider takes priority. Empty values fall back to LLM_MODEL.

    # Per-use-case model IDs (work with any provider, ideal for NIM's 40+ models)
    llm_model_chat: str = Field(
        default="deepseek-ai/deepseek-v4-flash", alias="LLM_MODEL_CHAT"
    )
    llm_model_analyst: str = Field(
        default="z-ai/glm-5.2", alias="LLM_MODEL_ANALYST"
    )
    llm_model_analyst_deep: str = Field(
        default="nvidia/nemotron-3-ultra-550b-a55b", alias="LLM_MODEL_ANALYST_DEEP"
    )
    llm_model_explain: str = Field(
        default="mistralai/mistral-medium-3.5-128b", alias="LLM_MODEL_EXPLAIN"
    )
    llm_model_extraction: str = Field(
        default="mistralai/mistral-medium-3.5-128b", alias="LLM_MODEL_EXTRACTION"
    )
    llm_model_judge: str = Field(
        default="deepseek-ai/deepseek-r1-0528", alias="LLM_MODEL_JUDGE"
    )

    # Optional: separate provider keys for direct API access (bypass NIM).
    # When a route's API key is set, that provider is used instead of NIM.
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    kimi_base_url: str = Field(
        default="https://api.moonshot.cn/v1", alias="KIMI_BASE_URL"
    )
    kimi_api_key: str = Field(default="", alias="KIMI_API_KEY")
    kimi_model: str = Field(default="moonshot-v1-8k", alias="KIMI_MODEL")

    glm_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4", alias="GLM_BASE_URL"
    )
    glm_api_key: str = Field(default="", alias="GLM_API_KEY")
    glm_model: str = Field(default="glm-4-flash", alias="GLM_MODEL")

    # Route overrides: "deepseek", "kimi", "glm", or empty.
    # Empty (default) = use primary provider with the per-use-case model above.
    llm_route_chat: str = Field(default="", alias="LLM_ROUTE_CHAT")
    llm_route_analyst: str = Field(default="", alias="LLM_ROUTE_ANALYST")
    llm_route_analyst_deep: str = Field(default="", alias="LLM_ROUTE_ANALYST_DEEP")
    llm_route_explain: str = Field(default="", alias="LLM_ROUTE_EXPLAIN")
    llm_route_extraction: str = Field(default="", alias="LLM_ROUTE_EXTRACTION")
    llm_route_judge: str = Field(default="", alias="LLM_ROUTE_JUDGE")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="alphaedge", alias="LANGSMITH_PROJECT")
    football_data_api_key: str = Field(default="", alias="FOOTBALL_DATA_API_KEY")
    odds_api_key: str = Field(default="", alias="ODDS_API_KEY")
    odds_api_sport_keys: str = Field(default="basketball_nba", alias="ODDS_API_SPORT_KEYS")
    odds_api_historical_snapshot_ats: str = Field(
        default="",
        alias="ODDS_API_HISTORICAL_SNAPSHOT_ATS",
    )
    polymarket_market_slugs: str = Field(default="", alias="POLYMARKET_MARKET_SLUGS")
    kalshi_market_tickers: str = Field(default="", alias="KALSHI_MARKET_TICKERS")
    polymarket_gamma_base_url: str = Field(
        default="https://gamma-api.polymarket.com", alias="POLYMARKET_GAMMA_BASE_URL"
    )
    kalshi_api_base_url: str = Field(
        default="https://api.elections.kalshi.com/trade-api/v2",
        alias="KALSHI_API_BASE_URL",
    )
    live_kalshi_series: str = Field(default="KXWCGAME", alias="LIVE_KALSHI_SERIES")
    kalshi_ws_enabled: bool = Field(default=True, alias="KALSHI_WS_ENABLED")
    kalshi_ws_url: str = Field(
        default="wss://api.elections.kalshi.com/trade-api/ws/v2",
        alias="KALSHI_WS_URL",
    )
    polymarket_ws_enabled: bool = Field(default=True, alias="POLYMARKET_WS_ENABLED")
    polymarket_ws_url: str = Field(
        default="wss://ws-subscriptions-clob.polymarket.com/ws/market",
        alias="POLYMARKET_WS_URL",
    )
    stream_reconnect_max_sec: float = Field(default=60.0, alias="STREAM_RECONNECT_MAX_SEC")
    stream_heartbeat_timeout_sec: float = Field(
        default=30.0, alias="STREAM_HEARTBEAT_TIMEOUT_SEC"
    )
    # Diff engine (T03)
    diff_engine_enabled: bool = Field(default=True, alias="DIFF_ENGINE_ENABLED")
    diff_state_backend: str = Field(default="memory", alias="DIFF_STATE_BACKEND")
    diff_price_jump_bps: float = Field(default=100.0, alias="DIFF_PRICE_JUMP_BPS")
    diff_orderbook_flip_ratio: float = Field(
        default=1.0, alias="DIFF_ORDERBOOK_FLIP_RATIO"
    )
    diff_volume_surge_min: float = Field(default=10_000.0, alias="DIFF_VOLUME_SURGE_MIN")
    # Alignment scorer (T04)
    alignment_enabled: bool = Field(default=True, alias="ALIGNMENT_ENABLED")
    alignment_window_sec: float = Field(default=600.0, alias="ALIGNMENT_WINDOW_SEC")
    alignment_min_score: float = Field(default=3.0, alias="ALIGNMENT_MIN_SCORE")
    alignment_min_layers: int = Field(default=3, alias="ALIGNMENT_MIN_LAYERS")
    alignment_weight_price: float = Field(default=1.0, alias="ALIGNMENT_WEIGHT_PRICE")
    alignment_weight_whale: float = Field(default=1.0, alias="ALIGNMENT_WEIGHT_WHALE")
    alignment_weight_news: float = Field(default=1.0, alias="ALIGNMENT_WEIGHT_NEWS")
    alignment_weight_model: float = Field(default=1.0, alias="ALIGNMENT_WEIGHT_MODEL")
    # News->price lag detector (T06)
    news_lag_enabled: bool = Field(default=True, alias="NEWS_LAG_ENABLED")
    news_lag_window_sec: float = Field(default=300.0, alias="NEWS_LAG_WINDOW_SEC")
    news_lag_min_relevance: float = Field(default=0.5, alias="NEWS_LAG_MIN_RELEVANCE")
    news_lag_move_threshold: float = Field(default=0.02, alias="NEWS_LAG_MOVE_THRESHOLD")
    # Analyst agent (T07)
    analyst_enabled: bool = Field(default=True, alias="ANALYST_ENABLED")
    analyst_cooldown_sec: float = Field(default=900.0, alias="ANALYST_COOLDOWN_SEC")
    prompt_version: str = Field(default="v1", alias="PROMPT_VERSION")
    # Eval harness (T08)
    eval_claim_epsilon: float = Field(default=0.02, alias="EVAL_CLAIM_EPSILON")
    # Macro desk (E11) — FRED economic data; World Bank is the keyless fallback
    fred_api_key: str = Field(default="", alias="FRED_API_KEY")
    # Alert dispatch (T09) — external channels OFF by default
    alerts_telegram_enabled: bool = Field(default=False, alias="ALERTS_TELEGRAM_ENABLED")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    alerts_webhook_url: str = Field(default="", alias="ALERTS_WEBHOOK_URL")
    # Scheduled research loop (T10)
    research_top_n: int = Field(default=10, alias="RESEARCH_TOP_N")
    research_lookback_hours: float = Field(default=24.0, alias="RESEARCH_LOOKBACK_HOURS")
    # ML model selection (T11) — "xgboost" (default) | "lightgbm" (optional dep)
    ml_model_type: str = Field(default="xgboost", alias="ML_MODEL_TYPE")
    # Instability signal (T13) — feature/context only, OFF by default
    instability_enabled: bool = Field(default=False, alias="INSTABILITY_ENABLED")
    instability_window_hours: float = Field(default=24.0, alias="INSTABILITY_WINDOW_HOURS")
    instability_half_life_hours: float = Field(default=12.0, alias="INSTABILITY_HALF_LIFE_HOURS")
    instability_threshold: float = Field(default=50.0, alias="INSTABILITY_THRESHOLD")
    # Feed instability as a forecasting feature (election/geopolitics markets only)
    instability_feature_enabled: bool = Field(
        default=False, alias="INSTABILITY_FEATURE_ENABLED"
    )
    # Daily digest distribution (T14) — push daily research to channels, OFF by default
    digest_distribution_enabled: bool = Field(
        default=False, alias="DIGEST_DISTRIBUTION_ENABLED"
    )
    # Multi-model ensemble + router (U08) — OFF by default (AutoLab-gated).
    # Flag stays OFF until walk-forward Brier of ensemble < single-model baseline.
    ensemble_enabled: bool = Field(default=False, alias="ENSEMBLE_ENABLED")
    # JSON string: {"NBA": "single", "Elections": "single", "default": "single"}
    # All categories default to "single" until the CLV gate passes.
    ensemble_router_config: str = Field(
        default="", alias="ENSEMBLE_ROUTER_CONFIG"
    )
    # U12 Calibration drift alarm — OFF by default.
    # When enabled, the drift service fires through the EXISTING T09 AlertDispatchService.
    # Zero external calls when both drift_alarm_enabled=false AND the T09 external channels
    # are also disabled (default state).
    drift_alarm_enabled: bool = Field(default=False, alias="DRIFT_ALARM_ENABLED")
    drift_alarm_threshold: float = Field(
        default=0.05,
        alias="DRIFT_ALARM_THRESHOLD",
        description="Absolute Brier drift above baseline that triggers the alarm.",
    )
    # Number of most-recent graded claims to include in the rolling Brier window.
    drift_rolling_window: int = Field(default=30, alias="DRIFT_ROLLING_WINDOW")
    # Backtest replay nightly job (U10) — OFF by default.
    # When enabled, runs a nightly replay on configured market slugs and publishes
    # results to backtest_runs for the track record.
    backtest_nightly_enabled: bool = Field(default=False, alias="BACKTEST_NIGHTLY_ENABLED")
    backtest_nightly_slugs: str = Field(
        default="nba-2025-01-15-lal-bos", alias="BACKTEST_NIGHTLY_SLUGS"
    )
    # U13 Trader profile (personalization) — ON by default (purely read/derive).
    # Set TRADER_PROFILE_ENABLED=false to return empty-state without a DB hit.
    trader_profile_enabled: bool = Field(default=True, alias="TRADER_PROFILE_ENABLED")
    kalshi_api_key_id: str = Field(default="", alias="KALSHI_API_KEY_ID")
    kalshi_signing_pem: str = Field(default="", alias="KALSHI_SIGNING_PEM")
    polygon_rpc_url: str = Field(default="", alias="POLYGON_RPC_URL")
    polymarket_subgraph_url: str = Field(default="", alias="POLYMARKET_SUBGRAPH_URL")
    tracked_wallet_addresses: str = Field(default="", alias="TRACKED_WALLET_ADDRESSES")

    @field_validator("paper_trading_only")
    @classmethod
    def must_be_paper_only(cls, v: bool) -> bool:
        if not v:
            raise ValueError("PAPER_TRADING_ONLY must be true for simulated-funds operation.")
        return v

    @model_validator(mode="after")
    def production_secrets_must_be_explicit(self) -> "Settings":
        if (
            self.app_env.strip().lower() in {"prod", "production", "staging"}
            and self.jwt_secret_key == "dev-jwt-secret-change-in-production"
        ):
            raise ValueError("JWT_SECRET_KEY must be set outside local development.")
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex(self) -> str:
        """Origins allowed in addition to the explicit CORS_ORIGINS list:
        localhost (any port) for dev, plus THIS app's Azure Static Web Apps
        origins — production AND the per-PR preview subdomains
        (e.g. ``proud-meadow-01b42b810-41.centralus.7.azurestaticapps.net``).
        Scoped to the app-name prefix so it is not an open
        ``*.azurestaticapps.net`` wildcard. Without the preview arm, every stage
        deploy is CORS-blocked and the frontend silently falls back to samples."""
        return (
            r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
            r"|https://proud-meadow-01b42b810(-\d+)?(\.[a-z0-9-]+)+\.azurestaticapps\.net"
        )

    @property
    def odds_api_sport_key_list(self) -> List[str]:
        return self._csv_list(self.odds_api_sport_keys)

    @property
    def odds_api_historical_snapshot_at_list(self) -> List[str]:
        return self._csv_list(self.odds_api_historical_snapshot_ats)

    @property
    def polymarket_market_slug_list(self) -> List[str]:
        return self._csv_list(self.polymarket_market_slugs)

    @property
    def kalshi_market_ticker_list(self) -> List[str]:
        return self._csv_list(self.kalshi_market_tickers)

    @property
    def tracked_wallet_address_list(self) -> List[str]:
        return self._csv_list(self.tracked_wallet_addresses)

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
