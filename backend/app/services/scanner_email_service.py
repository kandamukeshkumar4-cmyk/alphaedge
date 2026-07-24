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


def _resolve_smtp(settings):
    """Return (host, port, user, password, from_addr, to_addr) or None."""
    if not smtp_configured(settings):
        return None
    host = str(settings.smtp_host).strip()
    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = (getattr(settings, "smtp_user", "") or "").strip()
    password = getattr(settings, "smtp_pass", "") or ""
    from_addr = (getattr(settings, "smtp_from", "") or "").strip() or (
        user or "noreply@localhost"
    )
    to_addr = str(settings.alert_email_to).strip()
    return host, port, user, password, from_addr, to_addr


def _deliver(
    msg: EmailMessage,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    smtp_factory=None,
) -> bool:
    """Open one SMTP session and send exactly one message."""
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
        logger.warning("scanner email send failed", exc_info=True)
        return False


def send_scanner_fired_email(
    scanner: Scanner,
    run: ScannerRun,
    *,
    settings=None,
    smtp_factory=None,
) -> bool:
    """Send a plain-text fired summary. Returns True if sent, False if skipped."""
    settings = settings or get_settings()
    resolved = _resolve_smtp(settings)
    if resolved is None:
        return False
    host, port, user, password, from_addr, to_addr = resolved

    result = run.result if isinstance(run.result, dict) else {}
    top = result.get("top_pick") if isinstance(result.get("top_pick"), dict) else {}
    pick_title = str(top.get("title") or top.get("market_slug") or "alert")
    subject = f"{scanner.name}: {pick_title}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(build_fired_email_body(scanner, run))

    return _deliver(
        msg, host=host, port=port, user=user, password=password, smtp_factory=smtp_factory
    )


def build_test_email_body(scanner: Scanner) -> str:
    lines = [
        f"This is a test alert from {scanner.name}.",
        "If you received this, scanner email delivery is configured correctly.",
        "",
        PAPER_FOOTER,
    ]
    return "\n".join(lines)


def send_scanner_test_email(
    scanner: Scanner,
    *,
    settings=None,
    smtp_factory=None,
) -> bool:
    """Send exactly ONE pre-publish configuration-check email (loop86 F-B).

    Returns True if sent, False if SMTP is unconfigured or delivery failed.
    Paper research only — never tied to a run or an alert.
    """
    settings = settings or get_settings()
    resolved = _resolve_smtp(settings)
    if resolved is None:
        return False
    host, port, user, password, from_addr, to_addr = resolved

    msg = EmailMessage()
    msg["Subject"] = (
        f"Test alert from {scanner.name} — configuration check, paper research only"
    )
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(build_test_email_body(scanner))

    return _deliver(
        msg, host=host, port=port, user=user, password=password, smtp_factory=smtp_factory
    )


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


def send_plain_text_email(
    *,
    to_addr: str,
    subject: str,
    body: str,
    settings=None,
    smtp_factory=None,
) -> bool:
    """Send one plain-text email via the shared SMTP helper.

    Skips silently when SMTP is unconfigured or ``to_addr`` is empty.
    Paper research only — never places orders.
    """
    settings = settings or get_settings()
    if not smtp_configured(settings):
        return False
    dest = (to_addr or "").strip()
    if not dest:
        return False
    resolved = _resolve_smtp(settings)
    if resolved is None:
        return False
    host, port, user, password, from_addr, _default_to = resolved

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = dest
    msg.set_content(body)
    return _deliver(
        msg, host=host, port=port, user=user, password=password, smtp_factory=smtp_factory
    )
