from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.security import (
    clear_access_cookie,
    create_access_token,
    hash_password,
    set_access_cookie,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserProfileResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UpdateMeRequest(BaseModel):
    onboarded: bool | None = None
    display_name: str | None = Field(default=None, max_length=32)


class UpdateMeResponse(BaseModel):
    onboarded: bool
    display_name: str | None


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == body.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    token = create_access_token(str(user.id))
    # H-SEC-02: also set the httpOnly cookie. Body token stays for API/dev use.
    set_access_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(str(user.id))
    set_access_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    """Clear the httpOnly session cookie (H-SEC-02). Bearer clients simply drop
    their token client-side; this exists so cookie sessions can be ended."""
    clear_access_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserProfileResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        paper_balance=float(current_user.paper_balance),
        created_at=current_user.created_at,
    )


@router.patch("/me", response_model=UpdateMeResponse)
async def update_me(
    body: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateMeResponse:
    if body.onboarded is not None:
        current_user.onboarded = body.onboarded
    if body.display_name is not None:
        if len(body.display_name) > 32:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="display_name must be 32 characters or fewer",
            )
        current_user.display_name = body.display_name
    await db.flush()
    return UpdateMeResponse(
        onboarded=current_user.onboarded,
        display_name=current_user.display_name,
    )
