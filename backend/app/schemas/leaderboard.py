from pydantic import BaseModel, Field


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    realized_pnl: float
    total_trades: int
    win_rate: float


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry] = Field(default_factory=list)
