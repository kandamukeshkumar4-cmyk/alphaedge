import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    paper_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("100000"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    display_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    paper_orders: Mapped[list["PaperOrder"]] = relationship(back_populates="user")


class PaperOrder(Base):
    """A JWT-user's paper-trade ledger entry (slug/side/cost/realized_pnl/settled).

    NOT a duplicate of ``Order``: that models the CLOB matching-engine order
    (account-based, order_type, price/quantity, filled_quantity, fills). They
    are distinct domain concepts with different lifecycles and consumers, so the
    long-standing "PaperOrder/Order consolidation" (C1/E09) is deliberately NOT
    done — merging them would be an architectural error, not a cleanup.
    """

    __tablename__ = "paper_orders"
    __table_args__ = (Index("ix_paper_orders_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    side: Mapped[str] = mapped_column(String(3), nullable=False)
    outcome: Mapped[str] = mapped_column(String(3), nullable=False, default="yes")
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    action: Mapped[str] = mapped_column(String(4), nullable=False, default="BUY", server_default="BUY")
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    settled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="paper_orders")


class MarketResolution(Base):
    __tablename__ = "market_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(3), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    tournament_tag: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="seed", server_default="seed")
    external_slug: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    clob_token_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    """A per-account market signal/watchlist marker (unique per account+market).

    NOT a duplicate of ``signal_events``: that stores pipeline-generated diff/
    whale/news DeltaEvents (signal_type/platform/payload). Different producers,
    different schema, different consumers — so the "PaperSignal → signal_events
    fold" (C2/E09) is deliberately NOT done.
    """

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
    settled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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
    __table_args__ = (
        Index(
            "ix_odds_snapshots_market_source_captured",
            "market_slug",
            "source",
            "captured_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_slug: Mapped[str] = mapped_column(String(128), index=True)
    implied_yes: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    source: Mapped[str] = mapped_column(String(64), default="fixture")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    book: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    platform_market_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    market_type: Mapped[str] = mapped_column(String(32), default="binary")
    outcome_name: Mapped[str] = mapped_column(String(128), default="Yes")
    line: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    close_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


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
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # T11 SHAP top features
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


class SignalEvent(Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        Index("ix_signal_events_type_market", "signal_type", "platform", "market_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    market_id: Mapped[str] = mapped_column(String(128), nullable=False)
    headline_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WeatherForecastLog(Base):
    """O05: one row per (city, target_date) recording the NWS forecast high and
    the sigma the bucket model used, so the observed high can be filled in later
    and forecast-vs-actual error learned. Pure record-keeping — never an order.

    The learned-sigma application stays OFF until enough resolved pairs exist
    (data-gated); this table just accumulates the evidence."""

    __tablename__ = "weather_forecast_logs"
    __table_args__ = (
        UniqueConstraint("city", "target_date", name="uq_weather_forecast_city_date"),
        Index("ix_weather_forecast_target_date", "target_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    target_date: Mapped[Any] = mapped_column(Date, nullable=False)
    forecast_high_f: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    sigma_used: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    actual_high_f: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="nws.point-forecast")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TrackedWallet(Base):
    __tablename__ = "tracked_wallets"
    __table_args__ = (Index("ix_tracked_wallets_qualified_roi", "qualified", "roi"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), default="")
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    roi: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    hit_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    qualified: Mapped[bool] = mapped_column(Boolean, default=False)
    wallet_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    positions: Mapped[list["WalletPosition"]] = relationship(back_populates="tracked_wallet")


class WalletPosition(Base):
    __tablename__ = "wallet_positions"
    __table_args__ = (
        Index("ix_wallet_positions_market", "platform", "market_id"),
        Index("ix_wallet_positions_wallet_market", "tracked_wallet_id", "platform", "market_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracked_wallet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracked_wallets.id"))
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    market_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    average_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    position_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tracked_wallet: Mapped["TrackedWallet"] = relationship(back_populates="positions")


class WalletPositionSnapshot(Base):
    """T05 time-series of a whale's positions, for diffing into whale_delta events.

    Distinct from WalletPosition (current state): this is append-only history keyed
    by (wallet_address, market_slug, captured_at) so consecutive snapshots can be
    diffed to detect adds/exits/flips.
    """

    __tablename__ = "wallet_position_snapshots"
    __table_args__ = (
        Index(
            "ix_wallet_pos_snap_wallet_market_captured",
            "wallet_address",
            "market_slug",
            "captured_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), default="YES")
    size: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    avg_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnalystBrief(Base):
    """T07 AI research brief generated on an analyst.trigger."""

    __tablename__ = "analyst_briefs"
    __table_args__ = (
        Index("ix_analyst_briefs_market_created", "market_slug", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    headline: Mapped[str] = mapped_column(String(160), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(64), default="unknown")
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    generator: Mapped[str] = mapped_column(String(16), default="llm")
    kind: Mapped[str] = mapped_column(String(16), default="brief")  # brief | digest
    # E13 analyst persona lens: macro | whale-flow | news | NULL (default desk)
    persona: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    claim: Mapped[Optional["BriefClaim"]] = relationship(
        back_populates="brief", uselist=False
    )


class BriefClaim(Base):
    """The falsifiable claim attached to a brief; graded by the eval harness (T08)."""

    __tablename__ = "brief_claims"
    __table_args__ = (
        Index("ix_brief_claims_status_horizon", "status", "horizon_minutes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyst_briefs.id"))
    market_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    horizon_minutes: Mapped[int] = mapped_column(Integer, default=60)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    price_at_claim: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    resolution_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    brief: Mapped["AnalystBrief"] = relationship(back_populates="claim")


class AnalystEvalAggregate(Base):
    """T08 public track-record aggregate: accuracy/Brier per dimension + window."""

    __tablename__ = "analyst_eval_aggregates"
    __table_args__ = (
        Index("ix_analyst_eval_dimension_key_window", "dimension", "dim_key", "window_days"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)  # category|claim_type|model_version|prompt_version|overall
    dim_key: Mapped[str] = mapped_column(String(64), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, default=7)  # 7 | 30 | 0 (all)
    n: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    brier: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0"))
    provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    __table_args__ = (Index("ix_job_runs_job_started", "job_name", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


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
    """Pseudonymous forecaster identity. We only store hashes, never raw secrets."""

    __tablename__ = "forecasters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    recovery_code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    recovery_email_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecasts: Mapped[list["ForecastLog"]] = relationship(back_populates="forecaster")


class ExternalMarket(Base):
    """A market on an external platform (Polymarket/Kalshi). Implied price and
    resolution are sourced API-first, not scraped from the DOM."""

    __tablename__ = "external_markets"
    __table_args__ = (
        Index("ix_external_markets_platform_external_id", "platform", "external_id", unique=True),
        Index("ix_external_markets_status", "status"),
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


class MarketSnapshot(Base):
    """API/manual market state captured at lock time.

    This preserves what AlphaEdge knew at the moment of the forecast without
    giving the extension authority to mutate external-market metadata later.
    """

    __tablename__ = "market_snapshots"
    __table_args__ = (Index("ix_market_snapshots_market_captured", "external_market_id", "captured_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_market_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_markets.id"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(
        _pg_enum(Platform, name="platform", create_type=False), nullable=False
    )
    implied_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="manual")
    snapshot_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
        Index(
            "ix_forecast_logs_forecaster_idempotency",
            "forecaster_id",
            "idempotency_key",
            unique=True,
        ),
        Index("ix_forecast_logs_forecaster_id", "forecaster_id"),
        Index("ix_forecast_logs_forecaster_locked", "forecaster_id", "locked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    forecaster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forecasters.id"), nullable=False)
    external_market_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_markets.id"), nullable=False
    )
    market_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("market_snapshots.id"), nullable=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    platform: Mapped[Platform] = mapped_column(
        _pg_enum(Platform, name="platform", create_type=False), nullable=False
    )
    market_url: Mapped[str] = mapped_column(String(512), default="")
    outcome_label: Mapped[str] = mapped_column(String(128), default="YES")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
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
    snapshot_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    time_to_resolution_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    forecaster: Mapped["Forecaster"] = relationship(back_populates="forecasts")
    external_market: Mapped["ExternalMarket"] = relationship(back_populates="forecasts")
    market_snapshot: Mapped[Optional["MarketSnapshot"]] = relationship()
    score: Mapped[Optional["ForecastScore"]] = relationship(
        back_populates="forecast", uselist=False
    )


class AgentClone(Base):
    """U06 — User-composed agent clone: a saved configuration of a SUBSET of
    the vetted GRAPH_NODES plus execution params.  Editing creates a new version
    (version increments); old versions are retained as separate rows with the
    same clone_id but a higher version number."""

    __tablename__ = "agent_clones"
    __table_args__ = (
        Index("ix_agent_clones_clone_id_version", "clone_id", "version", unique=True),
        Index("ix_agent_clones_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stable identifier across versions — all versions share the same clone_id.
    clone_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # JSON-serialised list[str] of vetted GRAPH_NODE names (server-validated on write).
    nodes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    # Watched market slugs / category strings (JSON list[str]).
    markets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Edge threshold: 0.0–0.50, clamped on write.
    edge_threshold: Mapped[float] = mapped_column(Numeric(5, 4), default=0.05)
    # Cooldown between runs in minutes: 60–10080 (1h–7d), clamped on write.
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    # is_latest flag — only the newest version per clone_id is True.
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    # paper-only enforcement annotation (non-functional; checked in runner).
    paper_trading_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    runs: Mapped[list["AgentCloneRun"]] = relationship(
        back_populates="clone", foreign_keys="AgentCloneRun.clone_version_id"
    )


class AgentCloneRun(Base):
    """U06 — A single paper-mode execution of an AgentClone on a specific market."""

    __tablename__ = "agent_clone_runs"
    __table_args__ = (
        Index("ix_agent_clone_runs_clone_id_created", "clone_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The specific clone version row that was executed.
    clone_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_clones.id"), nullable=False
    )
    # Stable clone_id for querying all runs across versions.
    clone_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    market_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|running|done|error
    # Serialised list of AgentTraceStep dicts.
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    # Subset of AgentState snapshot at end of run.
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    clone: Mapped["AgentClone"] = relationship(
        back_populates="runs", foreign_keys=[clone_version_id]
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


class BacktestRun(Base):
    """U10 — Stored result of a backtest replay over historical odds_snapshots.

    No order-path imports; paper-only simulation.  paper_trading_only is always True.
    """

    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_market_slug", "market_slug"),
        Index("ix_backtest_runs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    clone_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_equity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("10000"))
    final_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    spread: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0.02"))
    slippage_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 8), default=Decimal("0.001"))
    edge_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.05"))
    snapshot_count: Mapped[int] = mapped_column(Integer, default=0)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    brier_final: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    no_lookahead_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    insufficient_data: Mapped[bool] = mapped_column(Boolean, default=False)
    equity_curve: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    fill_quality: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    brier_over_time: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    paper_trading_only: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentMemory(Base):
    """loop3 — Resolved-market memory the agent graph can recall.

    One row per resolved market/forecast: what the model believed at close, what
    the market implied, the realized outcome and Brier, plus a short rationale so
    the "memory" graph node can surface similar past cases as reasoning context.

    ``embedding`` is an OPTIONAL JSON list of floats. It stays null unless an
    embedding provider is configured — the portable design never hard-depends on
    pgvector (Neon may not have it) and falls back to category/keyword recall.
    Memory is context-only: it never mutates probabilities or touches RiskService.
    """

    __tablename__ = "agent_memories"
    __table_args__ = (
        Index("ix_agent_memories_category_created", "category", "created_at"),
        Index("ix_agent_memories_slug", "market_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="General")
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)  # YES | NO | VOID
    model_prob_at_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_prob_at_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
