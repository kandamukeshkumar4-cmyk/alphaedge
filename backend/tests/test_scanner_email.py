"""C7 — optional SMTP on fired runs; skip when unconfigured."""
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import Scanner, ScannerRun
from app.services.scanner_email_service import maybe_email_scanner_fired


class _FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self):
        return True

    def starttls(self):
        return True

    def login(self, user, password):
        self.user = user
        self.password = password

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)


@pytest.fixture(autouse=True)
def _reset_sent():
    _FakeSMTP.sent = []
    yield
    _FakeSMTP.sent = []


def _scanner_and_run():
    scanner = Scanner(
        id=uuid4(),
        name="NBA confluence",
        description="email fixture",
        owner="tester",
        spec={"steps": []},
        status="active",
        cooldown_minutes=60,
    )
    top = {
        "market_slug": "nba-2025-01-15-lal-bos",
        "title": "Lakers vs Celtics",
        "aligned": True,
    }
    run = ScannerRun(
        id=uuid4(),
        scanner_id=scanner.id,
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        result={
            "candidates": [top],
            "top_pick": top,
            "counts": {"universe": 3, "candidates": 1, "aligned": 1},
        },
    )
    return scanner, run


def test_email_sends_when_smtp_configured():
    scanner, run = _scanner_and_run()
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_pass="pass",
        smtp_from="alerts@example.com",
        alert_email_to="desk@example.com",
    )
    sent = maybe_email_scanner_fired(
        scanner, run, settings=settings, smtp_factory=_FakeSMTP
    )
    assert sent is True
    assert len(_FakeSMTP.sent) == 1
    body = _FakeSMTP.sent[0].get_content()
    assert "NBA confluence" in body
    assert "Lakers vs Celtics" in body
    assert "aligned=1" in body
    assert "Paper research only" in body
    assert "no execution" in body


def test_email_skips_when_unconfigured():
    scanner, run = _scanner_and_run()
    settings = SimpleNamespace(
        smtp_host="",
        smtp_port=587,
        smtp_user="",
        smtp_pass="",
        smtp_from="",
        alert_email_to="",
    )
    sent = maybe_email_scanner_fired(
        scanner, run, settings=settings, smtp_factory=_FakeSMTP
    )
    assert sent is False
    assert _FakeSMTP.sent == []
