"""Audit H-SEC-01 (refreshed): tokenless access to the shared system/smoke
paper accounts is a local-dev convenience — prod/staging must reject it, or the
world can trade the shared bankroll (the default account ids are public).

Exercises the guard function directly: the HTTP stack adds a shared rate limiter
and a process-wide settings singleton, which make a full-suite request-level
assertion order-dependent. The guard is where the security decision lives.
"""

from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.v1 import routes

SYSTEM_ACCOUNT = UUID("00000000-0000-0000-0000-000000000001")
SMOKE_ACCOUNT = UUID("00000000-0000-0000-0000-000000000002")
OTHER_ACCOUNT = UUID("00000000-0000-0000-0000-0000000000ff")


@pytest.fixture
def app_env():
    """Mutate the exact settings object the guard reads. routes.py binds
    ``settings = get_settings()`` at import, so another test calling
    get_settings.cache_clear() would leave get_settings() returning a DIFFERENT
    instance than the guard uses — patch routes.settings directly."""
    settings = routes.settings
    original = settings.app_env
    yield lambda value: setattr(settings, "app_env", value)
    settings.app_env = original


@pytest.mark.parametrize("env", ["production", "prod", "staging", "PRODUCTION"])
@pytest.mark.parametrize("account_id", [SYSTEM_ACCOUNT, SMOKE_ACCOUNT])
def test_tokenless_shared_account_rejected_outside_local(app_env, env, account_id):
    app_env(env)
    with pytest.raises(HTTPException) as exc:
        routes._verify_paper_account_token(account_id, None)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("env", ["development", "test", "local", ""])
@pytest.mark.parametrize("account_id", [SYSTEM_ACCOUNT, SMOKE_ACCOUNT])
def test_tokenless_shared_account_allowed_in_local(app_env, env, account_id):
    app_env(env)
    # No exception: the dev/test convenience path lets the shared accounts through.
    routes._verify_paper_account_token(account_id, None)


def test_tokenless_non_shared_account_always_rejected(app_env):
    """A non-shared account without a token is rejected even in development."""
    app_env("development")
    with pytest.raises(HTTPException) as exc:
        routes._verify_paper_account_token(OTHER_ACCOUNT, None)
    assert exc.value.status_code == 401
