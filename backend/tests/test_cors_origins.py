"""CORS origin allow-list: dev localhost + this app's Azure SWA prod/preview.

Regression guard for the "deployed frontend shows only sample data" failure:
if the Azure Static Web Apps preview subdomains are not allowed, the browser
blocks every /api/v1 call and the UI silently falls back to samples.
"""

import re

from app.core.config import Settings


def _regex() -> re.Pattern[str]:
    settings = Settings(_env_file=None, PAPER_TRADING_ONLY=True)
    return re.compile(settings.cors_origin_regex)


def test_allows_localhost_any_port():
    rx = _regex()
    assert rx.fullmatch("http://localhost:3000")
    assert rx.fullmatch("http://127.0.0.1:8080")
    assert rx.fullmatch("https://localhost")


def test_allows_azure_swa_production_origin():
    rx = _regex()
    assert rx.fullmatch("https://proud-meadow-01b42b810.7.azurestaticapps.net")


def test_allows_azure_swa_pr_preview_origin():
    rx = _regex()
    # The per-PR stage URL the SWA bot posts on every pull request.
    assert rx.fullmatch(
        "https://proud-meadow-01b42b810-41.centralus.7.azurestaticapps.net"
    )


def test_rejects_foreign_azure_static_site():
    rx = _regex()
    # A different app on azurestaticapps.net must NOT be allowed (no open
    # wildcard — credentials are enabled).
    assert not rx.fullmatch("https://evil-app.7.azurestaticapps.net")
    assert not rx.fullmatch("https://proud-meadow-evil.attacker.net")
