from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import PAPER_TRADING_DISCLAIMER


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    paper_trading_only: bool = Field(default=True, alias="PAPER_TRADING_ONLY")
    # Loop V57: disabled by default. Pods are paper-only and started only by
    # the in-process runner when an operator explicitly enables this flag.
    pods_enabled: bool = Field(default=False, alias="PODS_ENABLED")
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
    # Loop V15 E1 — stricter identity-aware limit for mutating methods only
    # (POST/PUT/PATCH/DELETE). Keyed per bearer-token user (else client IP)
    # and per route. Admin-key requests are exempt. Default mirrors the
    # global limit so existing behavior is unchanged until ops tightens it.
    rate_limit_mutating: str = Field(default="600/minute", alias="RATE_LIMIT_MUTATING")
    rate_limit_mutating_enabled: bool = Field(
        default=True, alias="RATE_LIMIT_MUTATING_ENABLED"
    )
    # Loop V15 E2 — dedicated bearer token for the Prometheus /metrics scrape.
    # Empty (default) means /metrics accepts only the admin API key.
    metrics_token: str = Field(default="", alias="METRICS_TOKEN")
    # Loop V15 E3 — in-app ops alert thresholds (evaluated by workers/ops_alerts).
    ops_alert_error_rate_threshold: float = Field(
        default=0.05, alias="OPS_ALERT_ERROR_RATE_THRESHOLD"
    )
    ops_alert_min_requests: int = Field(default=50, alias="OPS_ALERT_MIN_REQUESTS")
    ops_alert_p99_ms: float = Field(default=1000.0, alias="OPS_ALERT_P99_MS")
    ops_alert_stale_prediction_hours: float = Field(
        default=12.0, alias="OPS_ALERT_STALE_PREDICTION_HOURS"
    )
    live_feed_enabled: bool = Field(default=True, alias="LIVE_FEED_ENABLED")
    live_tick_interval_sec: int = Field(default=15, alias="LIVE_TICK_INTERVAL_SEC")
    # COST-01: when no client touched the API within the active window and no
    # price WebSocket is open, the tick loop slows to the idle interval so the
    # managed Postgres endpoint can suspend (Neon scale-to-zero needs >5 idle
    # minutes). It snaps back to the fast interval as soon as demand returns.
    live_tick_idle_interval_sec: int = Field(
        default=900, alias="LIVE_TICK_IDLE_INTERVAL_SEC"
    )
    live_tick_active_window_sec: int = Field(
        default=300, alias="LIVE_TICK_ACTIVE_WINDOW_SEC"
    )
    # COST-02: idle cadence for the delay-safe periodic loops (eval grading,
    # WC2026 resolution) when no client is active. Never below each loop's
    # fast interval (clamped in _paced_sleep).
    scheduler_idle_interval_sec: int = Field(
        default=3600, alias="SCHEDULER_IDLE_INTERVAL_SEC"
    )
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
    scheduler_news_mispricing_enabled: bool = Field(
        default=True, alias="SCHEDULER_NEWS_MISPRICING_ENABLED"
    )
    scheduler_unusual_flow_enabled: bool = Field(
        default=True, alias="SCHEDULER_UNUSUAL_FLOW_ENABLED"
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
    # V14 F02/F03: resolve past-close external markets from real venue settlement
    # (then score locked forecasts). Default on; bounded batch per pass.
    scheduler_external_resolve_enabled: bool = Field(
        default=True, alias="SCHEDULER_EXTERNAL_RESOLVE_ENABLED"
    )
    external_resolve_batch: int = Field(
        default=25, alias="EXTERNAL_RESOLVE_BATCH"
    )
    # V14 F04: auto-lock a LIVE model forecast on OPEN external markets nearing
    # close that lack one, so a genuine pre-close prediction exists to score.
    scheduler_external_autolock_enabled: bool = Field(
        default=True, alias="SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED"
    )
    external_autolock_batch: int = Field(
        default=25, alias="EXTERNAL_AUTOLOCK_BATCH"
    )
    # Loop V33 B2': register eligible INGESTED venue catalog markets as
    # ExternalMarket rows. Without this the autolock funnel is input-starved —
    # live ingest writes only `markets`, so `external_markets` had no automated
    # supply and autolock had nothing to select (see goals/loop-v33-lockbreadth).
    scheduler_external_market_bridge_enabled: bool = Field(
        default=True, alias="SCHEDULER_EXTERNAL_MARKET_BRIDGE_ENABLED"
    )
    external_market_bridge_batch: int = Field(
        default=25, alias="EXTERNAL_MARKET_BRIDGE_BATCH"
    )
    # V4-fix: in-process mirrors for tasks that otherwise only run under an
    # ARQ worker (prod runs uvicorn only). Flag-gated, default on.
    scheduler_drift_detect_enabled: bool = Field(
        default=True, alias="SCHEDULER_DRIFT_DETECT_ENABLED"
    )
    scheduler_ops_alerts_enabled: bool = Field(
        default=True, alias="SCHEDULER_OPS_ALERTS_ENABLED"
    )
    scheduler_portfolio_equity_enabled: bool = Field(
        default=True, alias="SCHEDULER_PORTFOLIO_EQUITY_ENABLED"
    )
    # Loop V24 N3: daily digest in-process loop (prod has no ARQ worker).
    scheduler_daily_digest_enabled: bool = Field(
        default=True, alias="SCHEDULER_DAILY_DIGEST_ENABLED"
    )
    # Loop V37 H3: JobRun retention sweep (flag-gated, default on).
    jobrun_retention_enabled: bool = Field(
        default=True, alias="JOBRUN_RETENTION_ENABLED"
    )
    jobrun_retention_days: int = Field(default=30, alias="JOBRUN_RETENTION_DAYS")
    scheduler_jobrun_retention_enabled: bool = Field(
        default=True, alias="SCHEDULER_JOBRUN_RETENTION_ENABLED"
    )
    # Loop V39: data retention (odds_snapshots downsample / signal_events /
    # notifications). Flag-gated with generous defaults; see R1 audit.
    data_retention_enabled: bool = Field(
        default=True, alias="DATA_RETENTION_ENABLED"
    )
    odds_snapshot_full_res_days: int = Field(
        default=90, alias="ODDS_SNAPSHOT_FULL_RES_DAYS"
    )
    signal_event_retention_days: int = Field(
        default=30, alias="SIGNAL_EVENT_RETENTION_DAYS"
    )
    notification_retention_days: int = Field(
        default=90, alias="NOTIFICATION_RETENTION_DAYS"
    )
    scheduler_data_retention_enabled: bool = Field(
        default=True, alias="SCHEDULER_DATA_RETENTION_ENABLED"
    )
    # Loop V24 N2: comma-separated user emails that receive ops/drift
    # notifications mirrored from AlertDispatchService (in-app only).
    notification_admin_emails: str = Field(
        default="", alias="NOTIFICATION_ADMIN_EMAILS"
    )
    external_autolock_window_sec: int = Field(
        default=86400, alias="EXTERNAL_AUTOLOCK_WINDOW_SEC"
    )
    # I03: in-process TTL micro-cache on the /api/v1/desk aggregate so the
    # market page's desk-panel polling can't hammer the free-tier Space.
    # Short TTL — it only absorbs the polling flood between changes.
    desk_cache_enabled: bool = Field(default=True, alias="DESK_CACHE_ENABLED")
    desk_cache_ttl_sec: float = Field(default=5.0, alias="DESK_CACHE_TTL_SEC")
    # Per-IP rate limit for the anonymous (no-token) assistant chat path.
    # Authenticated requests bypass this; anon demo traffic is bounded.
    # Higher default: HF/Vercel edges still occasionally share IPs even after
    # X-Forwarded-For parsing; 10/min was too tight for the public demo.
    assistant_anon_rate_per_min: int = Field(
        default=60, alias="ASSISTANT_ANON_RATE_PER_MIN"
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
    # Loop V31 L3 — which ESPN sports leagues the connector may poll (CSV).
    # Default nba preserves C2 single-league behavior. Signals only — never
    # resolves markets. Unknown keys in the CSV are ignored at parse time.
    sports_leagues_enabled: str = Field(default="nba", alias="SPORTS_LEAGUES_ENABLED")

    # News signals (last30days skill)
    news_signals_enabled: bool = Field(default=True, alias="NEWS_SIGNALS_ENABLED")
    news_signals_timeout: float = Field(default=25.0, alias="NEWS_SIGNALS_TIMEOUT")
    # Loop V61 S1: decide refreshes from observed urgency, while capping calls.
    news_cadence_enabled: bool = Field(default=True, alias="NEWS_CADENCE_ENABLED")
    news_cadence_budget: int = Field(default=10, alias="NEWS_CADENCE_BUDGET")
    news_cadence_price_jump: float = Field(default=0.05, alias="NEWS_CADENCE_PRICE_JUMP")
    news_cadence_whale_spike: float = Field(default=0.50, alias="NEWS_CADENCE_WHALE_SPIKE")
    # Optional API keys forwarded to last30days.py (all have free-tier fallbacks)
    scrapecreators_api_key: str = Field(default="", alias="SCRAPECREATORS_API_KEY")
    brave_api_key: str = Field(default="", alias="BRAVE_API_KEY")
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")

    # Loop V52 — Nemotron-3 NIM reasoning signal (optional graph feature; never a forecast)
    # Default model id verified 2026-07-16 at:
    # https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b
    # (free NIM API endpoint; OpenAI-compatible model string nvidia/nemotron-3-nano-30b-a3b)
    nemotron_signal_enabled: bool = Field(
        default=False, alias="NEMOTRON_SIGNAL_ENABLED"
    )
    nemotron_model: str = Field(
        default="nvidia/nemotron-3-nano-30b-a3b",
        alias="NEMOTRON_MODEL",
    )
    nemotron_signal_timeout: float = Field(
        default=30.0, alias="NEMOTRON_SIGNAL_TIMEOUT"
    )
    nemotron_prompt_version: str = Field(
        default="v1", alias="NEMOTRON_PROMPT_VERSION"
    )
    # V61 S3: opt-in, research-only hot-market lenses; missing NIM is honest off.
    sentiment_debate_enabled: bool = Field(default=False, alias="SENTIMENT_DEBATE_ENABLED")
    sentiment_debate_timeout: float = Field(default=20.0, alias="SENTIMENT_DEBATE_TIMEOUT")

    # Loop V58 D1 — whale flow (large-trade tape → whale_pressure feature)
    whale_flow_enabled: bool = Field(default=True, alias="WHALE_FLOW_ENABLED")
    whale_flow_interval_sec: int = Field(default=60, alias="WHALE_FLOW_INTERVAL_SEC")
    whale_flow_min_notional: float = Field(
        default=1000.0, alias="WHALE_FLOW_MIN_NOTIONAL"
    )
    whale_flow_trade_limit: int = Field(default=200, alias="WHALE_FLOW_TRADE_LIMIT")
    whale_flow_market_limit: int = Field(default=200, alias="WHALE_FLOW_MARKET_LIMIT")
    whale_flow_window_sec: float = Field(default=3600.0, alias="WHALE_FLOW_WINDOW_SEC")
    # Graph feature flag (D4): inject whale_pressure into prediction graph.
    whale_signal_enabled: bool = Field(default=False, alias="WHALE_SIGNAL_ENABLED")
    scheduler_whale_flow_enabled: bool = Field(
        default=True, alias="SCHEDULER_WHALE_FLOW_ENABLED"
    )

    # Loop V58 D2 — cross-venue implied gap refresh
    venue_gap_enabled: bool = Field(default=True, alias="VENUE_GAP_ENABLED")
    venue_gap_interval_sec: int = Field(default=60, alias="VENUE_GAP_INTERVAL_SEC")
    venue_gap_stale_after_sec: float = Field(
        default=300.0, alias="VENUE_GAP_STALE_AFTER_SEC"
    )
    venue_gap_min_confidence: float = Field(
        default=0.5, alias="VENUE_GAP_MIN_CONFIDENCE"
    )
    venue_gap_match_limit: int = Field(default=200, alias="VENUE_GAP_MATCH_LIMIT")
    scheduler_venue_gap_enabled: bool = Field(
        default=True, alias="SCHEDULER_VENUE_GAP_ENABLED"
    )

    # Loop V59 — code-only position heartbeat (no LLM). Default off.
    heartbeat_manager_enabled: bool = Field(
        default=False, alias="HEARTBEAT_MANAGER_ENABLED"
    )
    heartbeat_manager_interval_sec: int = Field(
        default=45, alias="HEARTBEAT_MANAGER_INTERVAL_SEC"
    )
    heartbeat_time_stop_sec: float = Field(
        default=86_400.0, alias="HEARTBEAT_TIME_STOP_SEC"
    )
    heartbeat_adverse_move_pct: float = Field(
        default=0.10, alias="HEARTBEAT_ADVERSE_MOVE_PCT"
    )
    heartbeat_profit_target_pct: float = Field(
        default=0.15, alias="HEARTBEAT_PROFIT_TARGET_PCT"
    )
    heartbeat_staleness_sec: float = Field(
        default=120.0, alias="HEARTBEAT_STALENESS_SEC"
    )
    heartbeat_tighten_adverse_pct: float = Field(
        default=0.05, alias="HEARTBEAT_TIGHTEN_ADVERSE_PCT"
    )
    # Reversible emergency gates (H3); default off / inactive.
    heartbeat_global_kill: bool = Field(
        default=False, alias="HEARTBEAT_GLOBAL_KILL"
    )
    heartbeat_daily_loss_halt_pct: float = Field(
        default=0.05, alias="HEARTBEAT_DAILY_LOSS_HALT_PCT"
    )

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
    # Loop V46 — open-events board ingest (kalshi_live_ingest.sync_open_events).
    # K1 audit: global /markets board is flooded by multigame parlays and never
    # intersects the open-events list (skipped=200). These knobs gate the fix
    # and honest widen without importing board junk.
    live_kalshi_per_category_limit: int = Field(
        default=10, alias="LIVE_KALSHI_PER_CATEGORY_LIMIT"
    )
    live_kalshi_max_markets_per_event: int = Field(
        default=8, alias="LIVE_KALSHI_MAX_MARKETS_PER_EVENT"
    )
    live_kalshi_event_market_fallback: bool = Field(
        default=True, alias="LIVE_KALSHI_EVENT_MARKET_FALLBACK"
    )
    live_kalshi_min_event_volume: int = Field(
        default=0, alias="LIVE_KALSHI_MIN_EVENT_VOLUME"
    )
    live_kalshi_open_events_limit: int = Field(
        default=200, alias="LIVE_KALSHI_OPEN_EVENTS_LIMIT"
    )
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
    # News→mispricing (G03): |model_p − market_p| after fresh news
    news_mispricing_enabled: bool = Field(default=True, alias="NEWS_MISPRICING_ENABLED")
    news_mispricing_threshold: float = Field(default=0.05, alias="NEWS_MISPRICING_THRESHOLD")
    news_mispricing_window_sec: float = Field(
        default=900.0, alias="NEWS_MISPRICING_WINDOW_SEC"
    )
    # Unusual-flow anomaly (G04): price jump / volume spike with no news in window
    unusual_flow_enabled: bool = Field(default=True, alias="ANOMALY_UNUSUAL_FLOW_ENABLED")
    unusual_flow_window_sec: float = Field(
        default=900.0, alias="ANOMALY_UNUSUAL_FLOW_WINDOW_SEC"
    )
    # How far back the scan looks for recent delta:price_jump / delta:volume_surge
    # events (also the per-market anomaly dedupe horizon).
    unusual_flow_lookback_sec: float = Field(
        default=3600.0, alias="ANOMALY_UNUSUAL_FLOW_LOOKBACK_SEC"
    )
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
    # V51 A/B preflight. An operator must provide a non-secret reference to
    # Railway deployment/config history before a historic comparison can run.
    # Defaults deliberately refuse rather than infer historic runtime settings.
    ab_model_type_history_verified: bool = Field(
        default=False, alias="AB_MODEL_TYPE_HISTORY_VERIFIED"
    )
    ab_model_type_history_evidence: str = Field(
        default="", alias="AB_MODEL_TYPE_HISTORY_EVIDENCE"
    )
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
    # Multi-model ensemble + router (U08 / loop4).
    # Default ON: SAFE because the ensemble degrades to however many LLM keys are
    # configured (4 → 1 → 0). With 0 providers, or if every provider fails, the
    # prediction path falls back byte-identically to the single-model baseline.
    ensemble_enabled: bool = Field(default=True, alias="ENSEMBLE_ENABLED")
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
    # Loop V15 D2 — ForecastScore drift series (read-only consumer). Separate
    # from U12 BriefClaim drift so the two pipelines do not share state.
    forecast_drift_window: int = Field(default=50, alias="FORECAST_DRIFT_WINDOW")
    forecast_drift_baseline_brier: float = Field(
        default=0.25, alias="FORECAST_DRIFT_BASELINE_BRIER"
    )
    forecast_drift_baseline_ece: float = Field(
        default=0.10, alias="FORECAST_DRIFT_BASELINE_ECE"
    )
    forecast_drift_brier_threshold: float = Field(
        default=0.05, alias="FORECAST_DRIFT_BRIER_THRESHOLD"
    )
    forecast_drift_ece_threshold: float = Field(
        default=0.05, alias="FORECAST_DRIFT_ECE_THRESHOLD"
    )
    # Loop V15 D4 — scheduled XGBoost retrain on snapshot store. DEFAULT OFF.
    # Registers via D1 but NEVER auto-activates (human decision / E06).
    ml_retrain_enabled: bool = Field(default=False, alias="ML_RETRAIN_ENABLED")
    ml_retrain_min_rows: int = Field(default=20, alias="ML_RETRAIN_MIN_ROWS")
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
        if self.app_env.strip().lower() in {"prod", "production", "staging"}:
            if self.jwt_secret_key == "dev-jwt-secret-change-in-production":
                raise ValueError("JWT_SECRET_KEY must be set outside local development.")
            if self.admin_api_key == "dev-admin-key":
                raise ValueError("ADMIN_API_KEY must be set outside local development.")
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
            r"|https://alphaedge-frontend(-[a-z0-9-]+)?\.vercel\.app"
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
    def sports_leagues_enabled_list(self) -> List[str]:
        """CSV of league keys allowed for sports results polling (default nba)."""
        return [item.lower() for item in self._csv_list(self.sports_leagues_enabled)]

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
