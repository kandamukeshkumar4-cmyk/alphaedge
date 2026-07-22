"""Optional SMTP delivery for scanner fired summaries (research-only).

Uses stdlib smtplib only. Silently skips when SMTP is unconfigured.
Never places orders — emails are paper-research notifications.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.db.models import Scanner, ScannerRun

logger = logging.getLogger(__name__)

PAPER_FOOTER = "Paper research only — no execution"


def smtp_configured(settings=None) -> bool:
    settings = settings or get_settings()
    host = (getattr(settings, "smtp_host", "") or "").strip()
    to_addr = (getattr(settings, "alert_email_to", "") or "").strip()
    return bool(host and to_addr)


def build_fired_email_body(scanner: Scanner, run: ScannerRun) -> str:
    result = run.result if isinstance(run.result, dict) else {}
    top = result.get("top_pick") if isinstance(result.get("top_pick"), dict) else {}
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    pick_title = str(top.get("title") or top.get("market_slug") or "(none)")
    lines = [
        f"Scanner: {scanner.name}",
        f"Top pick: {pick_title}",
        (
            f"Counts: universe={counts.get('universe', 0)} "
            f"candidates={counts.get('candidates', 0)} "
            f"aligned={counts.get('aligned', 0)}"
        ),
        "",
        PAPER_FOOTER,
    ]
    return "\n".join(lines)


def send_scanner_fired_email(
    scanner: Scanner,
    run: ScannerRun,
    *,
    settings=None,
    smtp_factory=None,
) -> bool:
    """Send a plain-text fired summary. Returns True if sent, False if skipped."""
    settings = settings or get_settings()
    if not smtp_configured(settings):
        return False

    host = str(settings.smtp_host).strip()
    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = (getattr(settings, "smtp_user", "") or "").strip()
    password = getattr(settings, "smtp_pass", "") or ""
    from_addr = (getattr(settings, "smtp_from", "") or "").strip() or (
        user or "noreply@localhost"
    )
    to_addr = str(settings.alert_email_to).strip()

    result = run.result if isinstance(run.result, dict) else {}
    top = result.get("top_pick") if isinstance(result.get("top_pick"), dict) else {}
    pick_title = str(top.get("title") or top.get("market_slug") or "alert")
    subject = f"{scanner.name}: {pick_title}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(build_fired_email_body(scanner, run))

    factory = smtp_factory or smtplib.SMTP
    try:
        with factory(host, port, timeout=10) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except Exception:  # noqa: BLE001 — some servers have no TLS
                pass
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 — email must never break the run
        logger.warning("scanner fired email failed", exc_info=True)
        return False


def maybe_email_scanner_fired(
    scanner: Scanner,
    run: ScannerRun,
    *,
    settings=None,
    smtp_factory=None,
) -> bool:
    """Email only when the run has >=1 aligned candidate and SMTP is configured."""
    result = run.result if isinstance(run.result, dict) else {}
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    try:
        aligned = int(counts.get("aligned") or 0)
    except (TypeError, ValueError):
        aligned = 0
    if aligned < 1:
        return False
    return send_scanner_fired_email(
        scanner, run, settings=settings, smtp_factory=smtp_factory
    )
