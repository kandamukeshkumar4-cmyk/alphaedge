"""Contracts for platform usage summary (community layer)."""
from __future__ import annotations

from pydantic import BaseModel


class UsageDay(BaseModel):
    date: str
    sessions: int = 0
    skill_runs: int = 0
    scanner_runs: int = 0
    briefs: int = 0


class UsageTotals(BaseModel):
    sessions: int = 0
    skill_runs: int = 0
    scanner_runs: int = 0
    briefs: int = 0


class UsageSummaryOut(BaseModel):
    days: list[UsageDay]
    totals: UsageTotals
