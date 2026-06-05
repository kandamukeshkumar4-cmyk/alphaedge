from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import Settings
from app.data.connectors.base import NormalizedMarketSnapshot
from app.db.models import OddsSnapshot
from app.pipeline.ingest import (
    MarketDataConnectors,
    capture_configured_market_snapshots,
)
from app.workers import settings as worker_settings_module
from app.workers.tasks import WorkerSettings, capture_market_snapshots_task


CAPTURED_AT = datetime(2026, 1, 14, 18, tzinfo=timezone.utc)


class FakeOddsApiConnector:
    def __init__(self):
        self.calls: list[tuple[str, datetime]] = []

    def fetch_h2h_snapshots(
        self,
        sport_key: str,
        regions: str = "us",
        captured_at: datetime | None = None,
    ) -> list[NormalizedMarketSnapshot]:
        if captured_at is None:
            raise AssertionError("captured_at is required for deterministic capture")
        self.calls.append((sport_key, captured_at))
        return [
            NormalizedMarketSnapshot(
                market_slug=f"oddsapi:{sport_key}:draftkings:h2h:los-angeles-lakers",
                implied_yes=0.57,
                source="the-odds-api:draftkings",
                captured_at=captured_at,
                event_id="nba_lal_bos_2026_01_15",
                market_type="h2h",
                outcome_name="Los Angeles Lakers",
            ),
            NormalizedMarketSnapshot(
                market_slug=f"oddsapi:{sport_key}:draftkings:h2h:boston-celtics",
                implied_yes=0.43,
                source="the-odds-api:draftkings",
                captured_at=captured_at,
                event_id="nba_lal_bos_2026_01_15",
                market_type="h2h",
                outcome_name="Boston Celtics",
            ),
        ]


class FakeSingleMarketConnector:
    def __init__(self, source: str):
        self.source = source
        self.calls: list[tuple[str, datetime]] = []

    def fetch_market_snapshot(
        self,
        market_id: str,
        captured_at: datetime | None = None,
    ) -> NormalizedMarketSnapshot:
        if captured_at is None:
            raise AssertionError("captured_at is required for deterministic capture")
        self.calls.append((market_id, captured_at))
        return NormalizedMarketSnapshot(
            market_slug=f"{self.source}:{market_id.lower()}:yes",
            implied_yes=0.56,
            source=self.source,
            captured_at=captured_at,
            platform_market_id=market_id,
            title=market_id,
        )


class FailingSingleMarketConnector:
    def __init__(self, error: Exception):
        self.error = error

    def fetch_market_snapshot(
        self,
        market_id: str,
        captured_at: datetime | None = None,
    ) -> NormalizedMarketSnapshot:
        raise self.error


async def test_configured_market_snapshot_capture_persists_connector_rows(db_session):
    odds_api = FakeOddsApiConnector()
    polymarket = FakeSingleMarketConnector("polymarket.gamma")
    kalshi = FakeSingleMarketConnector("kalshi.rest")
    settings = Settings(
        ODDS_API_KEY="server-side-key",
        ODDS_API_SPORT_KEYS="basketball_nba",
        POLYMARKET_MARKET_SLUGS="will-lakers-beat-celtics",
        KALSHI_MARKET_TICKERS="KXNBA-LALBOS-26JAN15",
    )

    first = await capture_configured_market_snapshots(
        db_session,
        settings=settings,
        connectors=MarketDataConnectors(
            odds_api=odds_api,
            polymarket=polymarket,
            kalshi=kalshi,
        ),
        captured_at=CAPTURED_AT,
    )
    second = await capture_configured_market_snapshots(
        db_session,
        settings=settings,
        connectors=MarketDataConnectors(
            odds_api=odds_api,
            polymarket=polymarket,
            kalshi=kalshi,
        ),
        captured_at=CAPTURED_AT,
    )

    row_count = await db_session.scalar(select(func.count()).select_from(OddsSnapshot))
    sources = {
        source
        for (source,) in (
            await db_session.execute(select(OddsSnapshot.source).distinct())
        ).all()
    }
    assert first.fetched == 4
    assert first.inserted == 4
    assert first.skipped == 0
    assert second.fetched == 4
    assert second.inserted == 0
    assert second.skipped == 4
    assert row_count == 4
    assert sources == {"the-odds-api:draftkings", "polymarket.gamma", "kalshi.rest"}
    assert odds_api.calls == [
        ("basketball_nba", CAPTURED_AT),
        ("basketball_nba", CAPTURED_AT),
    ]
    assert polymarket.calls == [
        ("will-lakers-beat-celtics", CAPTURED_AT),
        ("will-lakers-beat-celtics", CAPTURED_AT),
    ]
    assert kalshi.calls == [
        ("KXNBA-LALBOS-26JAN15", CAPTURED_AT),
        ("KXNBA-LALBOS-26JAN15", CAPTURED_AT),
    ]


async def test_configured_market_snapshot_capture_records_source_failures(db_session):
    odds_api = FakeOddsApiConnector()
    kalshi = FakeSingleMarketConnector("kalshi.rest")
    settings = Settings(
        ODDS_API_KEY="server-side-key",
        ODDS_API_SPORT_KEYS="basketball_nba",
        POLYMARKET_MARKET_SLUGS="will-lakers-beat-celtics",
        KALSHI_MARKET_TICKERS="KXNBA-LALBOS-26JAN15",
    )

    result = await capture_configured_market_snapshots(
        db_session,
        settings=settings,
        connectors=MarketDataConnectors(
            odds_api=odds_api,
            polymarket=FailingSingleMarketConnector(RuntimeError("upstream 503")),
            kalshi=kalshi,
        ),
        captured_at=CAPTURED_AT,
    )

    row_count = await db_session.scalar(select(func.count()).select_from(OddsSnapshot))
    assert result.fetched == 3
    assert result.inserted == 3
    assert result.skipped == 0
    assert result.failed == 1
    assert len(result.failures) == 1
    assert result.failures[0].source == "polymarket.gamma"
    assert result.failures[0].target == "will-lakers-beat-celtics"
    assert result.failures[0].error == "upstream 503"
    assert row_count == 3


def test_settings_parse_market_snapshot_capture_targets():
    settings = Settings(
        ODDS_API_SPORT_KEYS="basketball_nba, americanfootball_nfl",
        POLYMARKET_MARKET_SLUGS="will-lakers-beat-celtics, election-market",
        KALSHI_MARKET_TICKERS="KXNBA-LALBOS-26JAN15, KXELECTION-2026",
    )

    assert settings.odds_api_sport_key_list == [
        "basketball_nba",
        "americanfootball_nfl",
    ]
    assert settings.polymarket_market_slug_list == [
        "will-lakers-beat-celtics",
        "election-market",
    ]
    assert settings.kalshi_market_ticker_list == [
        "KXNBA-LALBOS-26JAN15",
        "KXELECTION-2026",
    ]


def test_worker_settings_register_live_snapshot_capture_task():
    assert capture_market_snapshots_task in WorkerSettings.functions
    assert "app.workers.tasks.capture_market_snapshots_task" in (
        worker_settings_module.WorkerSettings.functions
    )
    cron_function_names = {
        getattr(getattr(job, "coroutine", None), "__name__", "")
        for job in WorkerSettings.cron_jobs
    }
    assert "capture_market_snapshots_task" in cron_function_names


async def test_capture_market_snapshots_task_reports_source_failures(monkeypatch):
    async def fake_capture_configured_market_snapshots(*args, **kwargs):
        from app.pipeline.ingest import (
            MarketSnapshotCaptureFailure,
            MarketSnapshotCaptureResult,
        )

        return MarketSnapshotCaptureResult(
            fetched=2,
            inserted=1,
            skipped=1,
            failures=(
                MarketSnapshotCaptureFailure(
                    source="kalshi.rest",
                    target="KXNBA-LALBOS-26JAN15",
                    error="upstream 500",
                ),
            ),
        )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def commit(self):
            return None

    class FakeSessionLocal:
        def __call__(self):
            return FakeSession()

    monkeypatch.setattr(
        "app.workers.tasks.capture_configured_market_snapshots",
        fake_capture_configured_market_snapshots,
    )
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", FakeSessionLocal())

    result = await capture_market_snapshots_task({"settings": Settings()})

    assert result == {
        "fetched": 2,
        "ingested": 1,
        "skipped": 1,
        "failed": 1,
        "failures": [
            {
                "source": "kalshi.rest",
                "target": "KXNBA-LALBOS-26JAN15",
                "error": "upstream 500",
            }
        ],
    }
