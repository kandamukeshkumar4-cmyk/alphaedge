from pydantic import BaseModel, Field


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    realized_pnl: float
    total_trades: int
    win_rate: float
    roi: float = 0.0


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry] = Field(default_factory=list)
    limit: int = 20
    offset: int = 0
    total: int = 0
    sort: str = "realized_pnl"
    cached: bool = False
