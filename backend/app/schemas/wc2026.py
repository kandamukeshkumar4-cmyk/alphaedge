from datetime import datetime

from pydantic import BaseModel, Field


class WC2026Match(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    kickoff_at: datetime
    venue: str
    stage_name: str
    p_home_win: float
    p_draw: float
    p_away_win: float
    markets: list[dict] = Field(default_factory=list)


class WC2026ScheduleResponse(BaseModel):
    matches: list[WC2026Match]
    generated_at: datetime


class WC2026SeedResponse(BaseModel):
    created: int
    skipped: int
    fixtures: int
