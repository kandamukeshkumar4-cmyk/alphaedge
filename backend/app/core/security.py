import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException, Response, status

from app.core.config import get_settings

# Audit H-SEC-02: the session token lives in an httpOnly cookie so page scripts
# (and any XSS) can't read it, unlike localStorage. Same-origin in production via
# the Vercel /api rewrite; Bearer stays supported for API clients + dev.
ACCESS_COOKIE_NAME = "ae_access"


def _cookie_secure() -> bool:
    # Secure cookies are dropped over plain http (local dev), so only set the
    # flag where the deploy is actually https.
    return get_settings().app_env.strip().lower() in {"prod", "production", "staging"}


def set_access_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


async def verify_admin_api_key(x_admin_api_key: str = Header(..., alias="X-Admin-API-Key")) -> str:
    settings = get_settings()
    if not secrets.compare_digest(x_admin_api_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )
    return x_admin_api_key
