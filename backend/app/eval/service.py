from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Evaluation,
    EvalAggregate,
    Market,
    OddsSnapshot,
    OrderOutcome,
    PredictionLog,
)
from app.events.bus import DomainEventBus


class EvalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.events = DomainEventBus(session)

    async def evaluate_market(self, market_id: UUID) -> Evaluation:
        result = await self.session.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one()
        if not market.winning_outcome:
            raise ValueError("Market not resolved")

        actual = 1 if market.winning_outcome == OrderOutcome.YES else 0

        pred_result = await self.session.execute(
            select(PredictionLog)
            .where(PredictionLog.market_slug == market.slug)
            .order_by(PredictionLog.predicted_at.desc())
            .limit(1)
        )
        pred_log = pred_result.scalar_one_or_none()
        predicted_prob = float(pred_log.predicted_prob) if pred_log else 0.5

        brier = (predicted_prob - actual) ** 2
        closing = await self._closing_implied(market, pred_log)

        ev = Evaluation(
            market_id=market_id,
            brier_score=Decimal(str(round(brier, 6))),
            predicted_prob=Decimal(str(round(predicted_prob, 4))),
            actual_outcome=actual,
            closing_implied=(
                Decimal(str(round(closing, 4))) if closing is not None else None
            ),
            pnl=Decimal("0"),
        )
        self.session.add(ev)
        await self.session.flush()

        await self.events.emit(
            "evaluation_generated",
            {"market_id": str(market_id), "brier_score": brier},
        )
        return ev

    async def _closing_implied(
        self,
        market: Market,
        pred_log: PredictionLog | None,
    ) -> float | None:
        snapshot_result = await self.session.execute(
            select(OddsSnapshot)
            .where(OddsSnapshot.market_slug == market.slug)
            .order_by(OddsSnapshot.captured_at.desc())
        )
        for snapshot in snapshot_result.scalars().all():
            if _is_pre_close_snapshot(snapshot, market):
                return _snapshot_probability(snapshot)

        if pred_log is None or pred_log.odds_snapshot_id is None:
            return None
        linked_snapshot = await self.session.get(OddsSnapshot, pred_log.odds_snapshot_id)
        if linked_snapshot is None or not _is_pre_close_snapshot(linked_snapshot, market):
            return None
        return _snapshot_probability(linked_snapshot)

    async def compute_aggregates(self, window_days: int = 7) -> EvalAggregate:
        """Legacy Evaluation table; public HTTP now uses forecast_scores."""
        result = await self.session.execute(select(Evaluation))
        evals = list(result.scalars().all())
        if not evals:
            mean_brier = Decimal("0")
            cal_err = Decimal("0")
        else:
            mean_brier = Decimal(str(sum(float(e.brier_score) for e in evals) / len(evals)))
            cal_err = _weighted_calibration_error(evals)

        agg = EvalAggregate(
            window_days=window_days,
            mean_brier=mean_brier,
            calibration_error=cal_err,
            market_count=len(evals),
        )
        self.session.add(agg)
        await self.session.flush()
        return agg

    def calibration_bins(self, evaluations: list[Evaluation], n_bins: int = 10) -> list[dict]:
        bins = [{"bin": i, "count": 0, "mean_pred": 0.0, "mean_outcome": 0.0} for i in range(n_bins)]
        for ev in evaluations:
            if ev.predicted_prob is None:
                continue
            idx = min(int(float(ev.predicted_prob) * n_bins), n_bins - 1)
            bins[idx]["count"] += 1
            bins[idx]["mean_pred"] += float(ev.predicted_prob)
            bins[idx]["mean_outcome"] += ev.actual_outcome
        for b in bins:
            if b["count"]:
                b["mean_pred"] /= b["count"]
                b["mean_outcome"] /= b["count"]
        return bins


def _weighted_calibration_error(evaluations: list[Evaluation], n_bins: int = 10) -> Decimal:
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for ev in evaluations:
        if ev.predicted_prob is None:
            continue
        predicted = float(ev.predicted_prob)
        idx = min(max(int(predicted * n_bins), 0), n_bins - 1)
        bins[idx].append((predicted, ev.actual_outcome))

    total = sum(len(items) for items in bins)
    if total == 0:
        return Decimal("0")

    weighted_error = 0.0
    for items in bins:
        if not items:
            continue
        mean_pred = sum(prediction for prediction, _ in items) / len(items)
        mean_outcome = sum(outcome for _, outcome in items) / len(items)
        weighted_error += (len(items) / total) * abs(mean_pred - mean_outcome)
    return Decimal(str(round(weighted_error, 6)))


def _is_pre_close_snapshot(snapshot: OddsSnapshot, market: Market) -> bool:
    close_at = snapshot.close_at or market.lock_at or market.resolved_at
    return close_at is None or snapshot.captured_at <= close_at


def _snapshot_probability(snapshot: OddsSnapshot) -> float:
    probability = snapshot.price if snapshot.price is not None else snapshot.implied_yes
    return float(probability)
