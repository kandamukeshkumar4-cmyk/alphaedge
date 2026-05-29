from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation, EvalAggregate, Market, OrderOutcome, PredictionLog
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
        closing = predicted_prob  # stub: use last prediction as closing proxy

        ev = Evaluation(
            market_id=market_id,
            brier_score=Decimal(str(round(brier, 6))),
            predicted_prob=Decimal(str(round(predicted_prob, 4))),
            actual_outcome=actual,
            closing_implied=Decimal(str(round(closing, 4))),
            pnl=Decimal("0"),
        )
        self.session.add(ev)
        await self.session.flush()

        await self.events.emit(
            "evaluation_generated",
            {"market_id": str(market_id), "brier_score": brier},
        )
        return ev

    async def compute_aggregates(self, window_days: int = 7) -> EvalAggregate:
        result = await self.session.execute(select(Evaluation))
        evals = list(result.scalars().all())
        if not evals:
            mean_brier = Decimal("0")
            cal_err = Decimal("0")
        else:
            mean_brier = Decimal(str(sum(float(e.brier_score) for e in evals) / len(evals)))
            cal_err = mean_brier  # simplified stub

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
