from pathlib import Path

from app import PAPER_TRADING_DISCLAIMER
from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_project_contract_supports_sports_and_election_paper_markets():
    settings = Settings()
    description = settings.openapi_description

    for text in [description, PAPER_TRADING_DISCLAIMER]:
        assert "paper-trading" in text
        assert "sports" in text.lower()
        assert "election" in text.lower()
        assert "NBA paper-trading prediction market simulation" not in text

    for text in [description, PAPER_TRADING_DISCLAIMER]:
        lowered = text.lower()
        assert "real-money" not in lowered
        assert "betting" not in lowered
        assert "wallet" not in lowered
        assert "wager" not in lowered


def test_repo_instructions_match_active_product_scope():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "NBA prediction market simulation only" not in agents
    assert "NBA, broader sports, and election" in agents
    assert "PAPER_TRADING_ONLY=true" in agents
    assert "RiskService` -> validated `OrderIntent` -> `OrderBookService" in agents
