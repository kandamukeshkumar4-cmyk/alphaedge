"""Loop112 — reachable venue matching per MATCHER-DIAG112 diagnosis.

The venue matcher ran every 60s with ``matched=0`` for 13+ hours in prod.
MATCHER-DIAG112.md found the cause: the score math was only reachable with
synthetic shared ``event_id`` + curated equal entity lists (fixture-shaped),
a hard date reject zeroed any differing ``lock_at`` calendar day (Kalshi
parks long-horizon markets on placeholder ends like 2045-01-01), and the
200-soonest scan window never even loaded the best human pairs.

Each test below pins one rule change from the fix plan with a case that
FAILED before loop112 (noted in its docstring) — plus the floors that keep
the matcher from going promiscuous: clearly-different pairs must still NOT
match, near-term different-day pairs must still hard-reject, and every
persisted row keeps its confidence + stale flag for downstream gating.

Paper-trading simulation only: no order path, no LLM calls, no secrets.
"""
from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.models import Market, MarketStatus, VenueMarketMatch
from app.services.venue_match_service import VenueMatchService
from app.signals.matching import (
    ResolutionTerms,
    _is_placeholder_end,
    match_resolution_terms,
    match_venue_markets,
    titles_share_content_token,
)


# Production phrasing from MATCHER-DIAG112.md pair set A (next Israeli PM).
A1_PM = "Will Itamar Ben Gvir be the next Prime Minister of Israel?"
A1_KS = "Who will succeed Netanyahu as Prime Minister of Israel?: Itamar Ben-Gvir"
A2_PM = "Will Yair Golan be the next Prime Minister of Israel?"
A2_KS = "Who will succeed Netanyahu as Prime Minister of Israel?: Yair Golan"
A3_PM = "Will Yariv Levin be the next Prime Minister of Israel?"
A3_KS = "Who will succeed Netanyahu as Prime Minister of Israel?: Yariv Levin"

# Prod-shaped placeholder locks: PM year-end default vs Kalshi New Year park.
PM_PLACEHOLDER_LOCK = datetime(2026, 12, 31, 23, 59, tzinfo=UTC)
KS_PLACEHOLDER_LOCK = datetime(2045, 1, 1, 0, 0, tzinfo=UTC)

# Catalog persist floor (loop112): match_open_catalog default. Direct
# callers (match_and_persist / match_venue_markets) keep the strict 0.75.
PERSIST_FLOOR = 0.50


def _venue_match(pm_title: str, ks_title: str, **overrides):
    """Score a prod-shaped pair: venue-native (never shared) external ids,
    defaulted entities, placeholder locks unless overridden."""
    kwargs = {
        "pm_slug": "pm-prod",
        "ks_slug": "ks-prod",
        "pm_close_time": PM_PLACEHOLDER_LOCK,
        "ks_close_time": KS_PLACEHOLDER_LOCK,
        "pm_event_id": "0x95f2c1a4-condition-id",  # Polymarket condition id
        "ks_event_id": "KXNISRAELPM-26",  # Kalshi ticker — different system
    }
    kwargs.update(overrides)
    return match_venue_markets(pm_title, ks_title, **kwargs)


# ---------------------------------------------------------------------------
# Fix 2 — placeholder ends soft-pass; sharp near-term days still hard-reject
# ---------------------------------------------------------------------------


class TestDateRuleSoftenedForPlaceholders:
    def test_placeholder_year_ends_do_not_hard_zero(self):
        """2026-12-31 vs 2045-01-01 is a venue placeholder disagreement, not
        evidence of different events.

        Failed before: hard reject → confidence 0.0, reason
        resolution_date_reject, no soft scoring ever ran.
        """
        match = _venue_match(A1_PM, A1_KS, min_confidence=PERSIST_FLOOR)
        assert match.confidence > 0.0
        assert "resolution_date_reject" not in match.reasons
        assert any(r.startswith("resolution_date_soft_pass") for r in match.reasons)

    def test_person_market_pair_a1_ben_gvir_now_confirms(self):
        """Diagnosis pair A1 — the strongest human match in the open catalog.

        Failed before: 0.00 (date reject); bypassing the reject gave 0.10 —
        0.75 was unreachable without a shared synthetic event_id.
        """
        match = _venue_match(A1_PM, A1_KS, min_confidence=PERSIST_FLOOR)
        assert match.status == "confirmed"
        assert match.confidence >= PERSIST_FLOOR
        assert "entity_match" in match.reasons
        assert "entity_person_name_match" in match.reasons
        assert any(r.startswith("title_token_match") for r in match.reasons)

    def test_person_market_pair_a2_golan_now_confirms(self):
        """Diagnosis pair A2 (production phrasing). Failed before: 0.00."""
        match = _venue_match(A2_PM, A2_KS, min_confidence=PERSIST_FLOOR)
        assert match.status == "confirmed"
        assert match.confidence >= PERSIST_FLOOR

    def test_person_market_pair_a3_levin_now_confirms(self):
        """Diagnosis pair A3 (production phrasing). Failed before: 0.00."""
        match = _venue_match(A3_PM, A3_KS, min_confidence=PERSIST_FLOOR)
        assert match.status == "confirmed"
        assert match.confidence >= PERSIST_FLOOR

    def test_sharp_two_days_apart_still_hard_rejects(self):
        """Floor: game 1 vs game 2 (real timestamps, 2 days apart) is two
        different events — G02 intent stays intact. Still rejects (unchanged).
        """
        match = _venue_match(
            "Will Lakers beat Celtics game 1?",
            "Lakers vs Celtics game 2",
            pm_close_time=datetime(2026, 1, 15, 0, 30, tzinfo=UTC),
            ks_close_time=datetime(2026, 1, 17, 0, 30, tzinfo=UTC),
            pm_event_id="nba-lal-bos-g1",
            ks_event_id="nba-lal-bos-g1",  # even a shared id must not survive
            min_confidence=PERSIST_FLOOR,
        )
        assert match.confidence == 0.0
        assert match.status == "unconfirmed"
        assert "resolution_date_reject" in match.reasons

    def test_sharp_months_apart_still_hard_rejects(self):
        """Floor: Fed June vs Fed September (both 18:00 sharp, 91 days) —
        different FOMC meetings, overlapping titles. Still rejects.
        """
        match = _venue_match(
            "Will the Fed cut rates in June?",
            "Fed rate cut September 2026?",
            pm_close_time=datetime(2026, 6, 18, 18, 0, tzinfo=UTC),
            ks_close_time=datetime(2026, 9, 17, 18, 0, tzinfo=UTC),
            min_confidence=PERSIST_FLOOR,
        )
        assert match.confidence == 0.0
        assert "resolution_date_reject" in match.reasons

    def test_adjacent_day_cross_midnight_is_not_fatal(self):
        """A game whose two venue timestamps straddle midnight (1h apart,
        1 day delta) is the same event.

        Failed before: hard reject → 0.0 despite the 1h close-time agreement.
        Floor check: it still does NOT confirm — soft scoring alone (0.20)
        stays well below the persist floor.
        """
        match = _venue_match(
            "Lakers vs Celtics tonight",
            "Will Lakers beat Celtics?",
            pm_close_time=datetime(2026, 1, 15, 23, 30, tzinfo=UTC),
            ks_close_time=datetime(2026, 1, 16, 0, 30, tzinfo=UTC),
            min_confidence=PERSIST_FLOOR,
        )
        assert "resolution_date_reject" not in match.reasons
        assert "close_time_match" in match.reasons
        assert match.status == "unconfirmed"
        assert match.confidence < PERSIST_FLOOR

    def test_placeholder_signature_detection(self):
        """The soft pass triggers only on venue-default end dates."""
        assert _is_placeholder_end(datetime(2045, 1, 1, 0, 0, 0, tzinfo=UTC))
        assert _is_placeholder_end(datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
        assert not _is_placeholder_end(datetime(2026, 1, 15, 0, 0, tzinfo=UTC))
        assert not _is_placeholder_end(datetime(2026, 1, 1, 0, 30, tzinfo=UTC))
        assert not _is_placeholder_end(datetime(2026, 6, 18, 18, 0, tzinfo=UTC))


# ---------------------------------------------------------------------------
# Fix 1 — entity near-match (Jaccard tiers + proper-name rule), persist floor
# ---------------------------------------------------------------------------


def _terms(entities: tuple[str, ...], title: str):
    return ResolutionTerms(
        platform="polymarket",
        market_id="m",
        title=title,
        event_id=None,
        normalized_entities=entities,
        close_at=None,
        resolution_source=None,
    )


class TestEntityNearMatch:
    def test_partial_jaccard_earns_partial_credit(self):
        """The diagnosis A1 entity sets: 6/11 shared → Jaccard 0.55.

        Failed before: boolean set equality → entity_mismatch, +0.0. Now the
        partial tier contributes exactly 0.20 (titles are disjoint here, so
        nothing else scores).
        """
        pm_ents = ("ben", "gvir", "israel", "itamar", "minister", "next", "prime")
        ks_ents = (
            "as", "ben", "gvir", "israel", "itamar",
            "minister", "netanyahu", "prime", "succeed", "who",
        )
        match = match_resolution_terms(
            _terms(pm_ents, title="one two three four"),
            _terms(ks_ents, title="five six seven eight"),
        )
        assert match.confidence == pytest.approx(0.20)
        assert any(r.startswith("entity_partial(jaccard=0.55") for r in match.reasons)

    def test_jaccard_boundaries(self):
        """Floors of the tiers: 0.80 → full, 0.50 → partial, below → nothing."""
        full = match_resolution_terms(
            _terms(("alpha", "beta", "gamma", "delta"), title="one two three"),
            _terms(("alpha", "beta", "gamma", "delta", "epsilon"), title="four five six"),
        )  # 4/5 = 0.80 exactly
        assert "entity_match" in full.reasons
        assert full.confidence == pytest.approx(0.40)

        partial = match_resolution_terms(
            _terms(("alpha", "beta"), title="one two three"),
            _terms(("alpha", "beta", "gamma", "delta"), title="four five six"),
        )  # 2/4 = 0.50 exactly
        assert any(r.startswith("entity_partial") for r in partial.reasons)
        assert partial.confidence == pytest.approx(0.20)

        mismatch = match_resolution_terms(
            _terms(("alpha", "beta", "gamma"), title="one two three"),
            _terms(("delta", "epsilon", "zeta"), title="four five six"),
        )
        assert "entity_mismatch" in mismatch.reasons
        assert mismatch.confidence == 0.0

    def test_same_candidate_name_earns_full_entity_credit(self):
        """Kalshi 'Event: Candidate' form: the right-hand proper name is the
        discriminating entity. Same person on both sides → full credit even
        though the full title-token sets differ.

        Failed before: full-set equality → entity_mismatch on every real
        person market (diagnosis structural issue #2).
        """
        match = _venue_match(A1_PM, A1_KS, min_confidence=PERSIST_FLOOR)
        assert "entity_match" in match.reasons
        assert "entity_person_name_match" in match.reasons

    def test_single_token_rhs_is_brand_overlap_not_person_match(self):
        """Floor: a one-token colon RHS ('...: Anthropic') must NOT fire the
        proper-name rule — that is brand overlap, not a same-question match.
        """
        match = _venue_match(
            "Will Anthropic's public ticker be $ANTH?",
            "Will OpenAI or Anthropic IPO first?: Anthropic",
            min_confidence=PERSIST_FLOOR,
        )
        assert "entity_person_name_match" not in match.reasons


# ---------------------------------------------------------------------------
# Controls — clearly-different pairs must still NOT match (no promiscuity)
# ---------------------------------------------------------------------------


class TestControlsStillUnconfirmed:
    def test_anthropic_ticker_vs_openai_ipo_not_matched(self):
        """Diagnosis pair set B control: shared brand name, different
        resolution questions. Must stay unconfirmed (and scores 0.0).
        """
        match = _venue_match(
            "Will Anthropic's public ticker be $ANTH?",
            "Will OpenAI or Anthropic IPO first?: Anthropic",
            min_confidence=PERSIST_FLOOR,
        )
        assert match.status == "unconfirmed"
        assert match.confidence < PERSIST_FLOOR

    def test_spacex_market_cap_vs_mars_landing_not_matched(self):
        """Diagnosis pair set B control: same company, different events."""
        match = _venue_match(
            "Will SpaceX have the largest market cap on Dec 31?",
            "Will SpaceX land on Mars before 2030?",
            ks_close_time=datetime(2030, 1, 1, 0, 0, tzinfo=UTC),
            min_confidence=PERSIST_FLOOR,
        )
        assert match.status == "unconfirmed"
        assert match.confidence < PERSIST_FLOOR

    def test_canonical_same_event_still_confirms_at_strict_gate(self):
        """Regression: a fixture-shaped true pair (shared event id + curated
        equal entities + same close) still clears the original strict 0.75.
        """
        match = match_venue_markets(
            "Will the Lakers beat the Celtics?",
            "Lakers beat Celtics?",
            pm_slug="pm-will-lakers-beat-celtics",
            ks_slug="ks-kxnba-lalbos-26jan15",
            pm_close_time=datetime(2026, 1, 15, 0, 30, tzinfo=UTC),
            ks_close_time=datetime(2026, 1, 15, 0, 30, tzinfo=UTC),
            pm_event_id="nba-lal-bos-2026-01-15",
            ks_event_id="nba-lal-bos-2026-01-15",
            pm_entities=("lakers", "celtics"),
            ks_entities=("lakers", "celtics"),
        )  # default min_confidence=0.75
        assert match.status == "confirmed"
        assert match.confidence >= 0.75


# ---------------------------------------------------------------------------
# Fix 1/3 — thresholds are persist-only; scan window tunable raised
# ---------------------------------------------------------------------------


class TestThresholdsAndTunables:
    def test_catalog_persist_floor_is_050_persist_only(self):
        """match_open_catalog persists at 0.50; the strict 0.75 stays the
        default for direct match_and_persist callers (G02 gate untouched).
        """
        catalog = inspect.signature(VenueMatchService.match_open_catalog)
        assert catalog.parameters["min_confidence"].default == 0.50
        direct = inspect.signature(VenueMatchService.match_and_persist)
        assert direct.parameters["min_confidence"].default == 0.75

    def test_venue_gap_match_limit_default_raised(self):
        """Plan Fix 3: the soonest-lock window must reach rank ~348 (Israel-PM
        PM market) — default raised from 200 into the 500–1000 range.
        """
        from app.core.config import Settings

        assert Settings.model_fields["venue_gap_match_limit"].default == 500


# ---------------------------------------------------------------------------
# Fix 3 — prefilter + per-pass stats (prod stops being a silent zero)
# ---------------------------------------------------------------------------


class TestPrefilter:
    def test_titles_share_content_token(self):
        assert titles_share_content_token(A1_PM, A1_KS)  # itamar/gvir/israel/...
        assert not titles_share_content_token(
            "Will Bitcoin hit 100k this week?", A1_KS
        )
        # Shared tokens exist but all under length 4 → filtered.
        assert not titles_share_content_token("Will the Fed win", "Fed cup")
        assert titles_share_content_token(
            "Will SpaceX reach orbit?", "SpaceX Starship orbital flight 2026"
        )


def _market(
    *,
    slug: str,
    source: str,
    title: str,
    external_id: str,
    lock_at: datetime,
) -> Market:
    return Market(
        slug=slug,
        title=title,
        question=title,
        source=source,
        external_id=external_id,
        status=MarketStatus.OPEN,
        lock_at=lock_at,
    )


@pytest.mark.asyncio
async def test_match_open_catalog_persists_person_pair_and_reports_stats(db_session):
    """End-to-end catalog pass on a prod-shaped mini catalog: one Israel-PM
    person pair (placeholder locks, venue-native ids) plus one unrelated
    BTC pair per venue.

    Failed before: the person pair hard-rejected to 0.0 on the placeholder
    date delta AND could not reach 0.75 anyway, so matched=0 with zero
    diagnostics — exactly the 13-hour silent-zero in prod.
    """
    near = datetime(2026, 7, 31, 16, 0, tzinfo=UTC)
    db_session.add(
        _market(
            slug="pm-next-pm-ben-gvir",
            source="polymarket",
            title=A1_PM,
            external_id="0x95f2c1a4-condition-id",
            lock_at=PM_PLACEHOLDER_LOCK,
        )
    )
    db_session.add(
        _market(
            slug="ks-succeed-netanyahu-ben-gvir",
            source="kalshi",
            title=A1_KS,
            external_id="KXNISRAELPM-26",
            lock_at=KS_PLACEHOLDER_LOCK,
        )
    )
    db_session.add(
        _market(
            slug="pm-btc-100k-week",
            source="polymarket",
            title="Will Bitcoin hit 100k this week?",
            external_id="0xbtc-weekly-condition",
            lock_at=near,
        )
    )
    db_session.add(
        _market(
            slug="ks-btc-100k-friday",
            source="kalshi",
            title="Bitcoin above 100k by Friday",
            external_id="KXBTC-26JUL31",
            lock_at=near,
        )
    )
    await db_session.commit()

    service = VenueMatchService(db_session)
    rows = await service.match_open_catalog()  # defaults: floor 0.50

    # The person pair persists; the BTC pair (one shared-word topic, different
    # question cadence) scores 0.20 and stays out.
    assert len(rows) == 1
    row = rows[0]
    assert row.pm_slug == "pm-next-pm-ben-gvir"
    assert row.ks_slug == "ks-succeed-netanyahu-ben-gvir"
    assert row.confidence >= PERSIST_FLOOR
    # Downstream gating stays intact: every row keeps confidence + stale flag.
    assert row.stale is False
    assert "entity_person_name_match" in row.reasons

    stored = list((await db_session.scalars(select(VenueMarketMatch))).all())
    assert len(stored) == 1
    assert stored[0].confidence == row.confidence

    # Per-pass diagnostics: visible instead of a silent zero.
    stats = service.last_scan_stats
    assert stats is not None
    assert stats["pm_scanned"] == 2
    assert stats["ks_scanned"] == 2
    # 2 of 4 combinations share a >=4-char token; the cross-topic ones skip.
    assert stats["pairs_scored"] == 2
    assert stats["pairs_skipped_prefilter"] == 2
    assert stats["date_rejects"] == 0  # placeholder delta soft-passes
    assert stats["below_threshold"] == 1  # the BTC pair
    assert stats["matched"] == 1
    assert stats["max_confidence"] >= PERSIST_FLOOR


@pytest.mark.asyncio
async def test_match_open_catalog_counts_date_rejects_in_stats(db_session):
    """A sharp near-term different-day pair (game 1 vs game 2, overlapping
    tokens) is still hard-rejected — and the pass now reports it instead of
    vanishing into matched=0.
    """
    db_session.add(
        _market(
            slug="pm-lakers-game1",
            source="polymarket",
            title="Will Lakers beat Celtics game 1?",
            external_id="pm-cond-g1",
            lock_at=datetime(2026, 1, 15, 0, 30, tzinfo=UTC),
        )
    )
    db_session.add(
        _market(
            slug="ks-lakers-game2",
            source="kalshi",
            title="Lakers vs Celtics game 2",
            external_id="KXNBA-G2",
            lock_at=datetime(2026, 1, 17, 0, 30, tzinfo=UTC),
        )
    )
    await db_session.commit()

    service = VenueMatchService(db_session)
    rows = await service.match_open_catalog()

    assert rows == []
    stats = service.last_scan_stats
    assert stats["pairs_scored"] == 1
    assert stats["date_rejects"] == 1
    assert stats["matched"] == 0
    assert stats["max_confidence"] == 0.0
