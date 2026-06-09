from typing import Literal

from pydantic import BaseModel


class CalibrationResponse(BaseModel):
    brier_score: float | None
    calibration_error: float | None
    markets_evaluated: int
    last_updated: str
    gate: Literal["pass", "fail", "no-data"]
    paper_trading_only: bool = True
