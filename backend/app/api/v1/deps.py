from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_COOKIE_NAME, verify_access_token
from app.db.models import User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)


def _resolve_token(
    credentials: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    """Audit H-SEC-02: accept the session token from the Authorization header
    (API clients, dev) OR the httpOnly ``ae_access`` cookie (browser). Bearer
    wins when both are present."""
    if credentials is not None:
        return credentials.credentials
    return cookie_token


async def _user_from_token(token: str, db: AsyncSession) -> User:
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    try:
        user_uuid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ae_access: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _resolve_token(credentials, ae_access)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await _user_from_token(token, db)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ae_access: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same auth as ``get_current_user`` but returns ``None`` when no token is
    presented, so an endpoint can keep an anonymous (rate-limited) public path
    while still honouring valid tokens. An *invalid* token still raises 401 —
    only the absence of a token is treated as anonymous.
    """
    token = _resolve_token(credentials, ae_access)
    if token is None:
        return None
    return await _user_from_token(token, db)
