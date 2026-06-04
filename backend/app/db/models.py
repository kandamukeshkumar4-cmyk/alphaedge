import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _pg_enum(enum_cls: type[enum.Enum], name: str, **kwargs: Any):
    """PostgreSQL ENUM columns must persist member values, not names."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        **kwargs,
    )


class MarketStatus(str, enum.Enum):
    OPEN = "open"
    LOCKED = "locked"
    RESOLVED = "resolved"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderOutcome(str, enum.Enum):
    YES = "yes"
    NO = "no"


class OrderType(str, enum.Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, enum.Enum):
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


class LedgerEntryType(str, enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRADE = "trade"
    SETTLEMENT = "settlement"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="account")
    positions: Mapped[list["Position"]] = relationship(back_populates="account")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="account")


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="Sports")
    icon: Mapped[str] = mapped_column(String(32), default="basketball")
    volume: Mapped[int] = mapped_column(Integer, default=0)
    traders: Mapped[int] = mapped_column(Integer, default=0)
    market_count: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[MarketStatus] = mapped_column(
        _pg_enum(MarketStatus, name="market_status"),
        default=MarketStatus.OPEN,
    )
    lock_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    winning_outcome: Mapped[Optional[OrderOutcome]] = mapped_column(
        _pg_enum(OrderOutcome, name="order_outcome", create_type=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="market")
    fills: Mapped[list["Fill"]] = relationship(back_populates="market")
    positions: Mapped[list["Position"]] = relationship(back_populates="market")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_market_status", "market_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    side: Mapped[OrderSide] = mapped_column(_pg_enum(OrderSide, name="order_side"))
    outcome: Mapped[OrderOutcome] = mapped_column(_pg_enum(OrderOutcome, name="order_outcome"))
    order_type: Mapped[OrderType] = mapped_column(_pg_enum(OrderType, name="order_type"))
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    status: Mapped[OrderStatus] = mapped_column(
        _pg_enum(OrderStatus, name="order_status"),
        default=OrderStatus.OPEN,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    market: Mapped["Market"] = relationship(back_populates="orders")
    account: Mapped["Account"] = relationship(back_populates="orders")


class PaperSignal(Base):
    __tablename__ = "paper_signals"
    __table_args__ = (
        Index("ix_paper_signals_account_market", "account_id", "market_id", unique=True),
        Index("ix_paper_signals_market_outcome", "market_id", "outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    outcome: Mapped[OrderOutcome] = mapped_column(
        _pg_enum(OrderOutcome, name="order_outcome", create_type=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    buy_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    sell_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    outcome: Mapped[OrderOutcome] = mapped_column(_pg_enum(OrderOutcome, name="order_outcome"))
    price: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    market: Mapped["Market"] = relationship(back_populates="fills")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (Index("ix_positions_account_market", "account_id", "market_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    yes_shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    no_shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    avg_yes_cost: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    avg_no_cost: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="positions")
    market: Mapped["Market"] = relationship(back_populates="positions")


class LedgerEntry(Base):
    __tablename__ = "ledger"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("markets.id"), nullable=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        _pg_enum(LedgerEntryType, name="ledger_entry_type")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="ledger_entries")


class DomainEvent(Base):
    __tablename__ = "domain_events"
    __table_args__ = (Index("ix_domain_events_type", "event_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Week 2+ tables
class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_slug: Mapped[str] = mapped_column(String(128), index=True)
    implied_yes: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    source: Mapped[str] = mapped_column(String(64), default="fixture")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_slug: Mapped[str] = mapped_column(String(128), index=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    feature_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    artifact_path: Mapped[str] = mapped_column(String(512))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureVersion(Base):
    __tablename__ = "feature_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    schema_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id"))
    dataset_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("dataset_snapshots.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="completed")
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    row_count: Mapped[int] = mapped_column(default=0)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("markets.id"), nullable=True)
    market_slug: Mapped[str] = mapped_column(String(128), index=True)
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )
    feature_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("feature_versions.id"), nullable=True
    )
    input_feature_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    odds_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("odds_snapshots.id"), nullable=True
    )
    predicted_prob: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.5"))
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lock_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)


# Week 3
class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"))
    brier_score: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    predicted_prob: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    actual_outcome: Mapped[int] = mapped_column(default=0)
    closing_implied: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalAggregate(Base):
    __tablename__ = "eval_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    window_days: Mapped[int] = mapped_column(default=7)
    mean_brier: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    calibration_error: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    market_count: Mapped[int] = mapped_column(default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Week 4
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    graph_version: Mapped[str] = mapped_column(String(32), default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"))
    step_name: Mapped[str] = mapped_column(String(64))
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FailedJob(Base):
    __tablename__ = "failed_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# AlphaEdge Mirror — forecast track-record ledger
class Platform(str, enum.Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    MANUAL = "manual"


class ExternalMarketStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class ForecastMode(str, enum.Enum):
    """LIVE = locked before resolution (counts toward real track record).
    PRACTICE = forecast made against an already-resolved market (onboarding only)."""

    LIVE = "live"
    PRACTICE = "practice"


class ForecastSource(str, enum.Enum):
    EXTENSION = "extension"
    WEB = "web"
    BACKFILL = "backfill"


class Forecaster(Base):
    """Pseudonymous forecaster identity. We only store hashes, never raw tokens/emails."""

    __tablename__ = "forecasters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    recovery_email_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecasts: Mapped[list["ForecastLog"]] = relationship(back_populates="forecaster")


class ExternalMarket(Base):
    """A market on an external platform (Polymarket/Kalshi). Implied price and
    resolution are sourced API-first, not scraped from the DOM."""

    __tablename__ = "external_markets"
    __table_args__ = (
        Index("ix_external_markets_platform_external_id", "platform", "external_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[Platform] = mapped_column(_pg_enum(Platform, name="platform"))
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(512), default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    category: Mapped[str] = mapped_column(String(64), default="Uncategorized")
    status: Mapped[ExternalMarketStatus] = mapped_column(
        _pg_enum(ExternalMarketStatus, name="external_market_status"),
        default=ExternalMarketStatus.OPEN,
    )
    close_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 1 == market resolved YES, 0 == resolved NO. Null until resolved.
    winning_outcome: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecasts: Mapped[list["ForecastLog"]] = relationship(back_populates="external_market")


class ForecastLog(Base):
    """Append-only, immutable locked forecast. A forecaster may lock multiple times
    on the same market (a belief update) — each is a new row with an incremented seq."""

    __tablename__ = "forecast_logs"
    __table_args__ = (
        Index(
            "ix_forecast_logs_forecaster_market_seq",
            "forecaster_id",
            "external_market_id",
            "seq",
            unique=True,
        ),
        Index("ix_forecast_logs_market", "external_market_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    forecaster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forecasters.id"), nullable=False)
    external_market_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_markets.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # P(market resolves YES) as believed by the forecaster.
    user_probability: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    # Market implied P(YES) snapshotted at lock time (API-first). Null if unavailable.
    market_implied_probability: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    snapshot_source: Mapped[str] = mapped_column(String(64), default="manual")
    # True when the forecast deviates from implied by >= the anchor epsilon (real signal).
    is_independent: Mapped[bool] = mapped_column(Boolean, default=True)
    mode: Mapped[ForecastMode] = mapped_column(
        _pg_enum(ForecastMode, name="forecast_mode"),
        default=ForecastMode.LIVE,
    )
    source: Mapped[ForecastSource] = mapped_column(
        _pg_enum(ForecastSource, name="forecast_source"),
        default=ForecastSource.WEB,
    )
    time_to_resolution_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    forecaster: Mapped["Forecaster"] = relationship(back_populates="forecasts")
    external_market: Mapped["ExternalMarket"] = relationship(back_populates="forecasts")
    score: Mapped[Optional["ForecastScore"]] = relationship(
        back_populates="forecast", uselist=False
    )


class ForecastScore(Base):
    """Resolution scoring for a single locked forecast. Written only after the
    external market resolves and the leakage gate passes."""

    __tablename__ = "forecast_scores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forecast_logs.id"), unique=True, nullable=False
    )
    actual_outcome: Mapped[int] = mapped_column(Integer, nullable=False)
    user_brier: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    market_brier: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    # market_brier - user_brier. Positive => forecaster beat the market.
    brier_delta: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    synthetic_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecast: Mapped["ForecastLog"] = relationship(back_populates="score")
