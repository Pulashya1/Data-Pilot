"""Email magic-link auth endpoints (MASTER_PROMPT.md §9, §12 Phase 8).

Passwordless: `POST /auth/request-link` mints a one-time `LoginToken` and emails it — or, with
no SMTP configured (the local-dev default), returns the link directly in the response and logs
it, so the whole flow works with zero external setup. `GET /auth/verify` consumes the token,
creates the `User` row on first login, and sets the signed session cookie
(`app/core/security.py`) that `app/api/deps.py::get_current_user` reads on every other route.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.email import send_magic_link_email
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.core.security import create_session_cookie, generate_login_token, hash_login_token
from app.models.user import LoginToken, User
from app.schemas.auth import RequestLinkRequest, RequestLinkResponse, UserOut

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit)])


@router.post("/request-link", response_model=RequestLinkResponse)
async def request_link(
    body: RequestLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RequestLinkResponse:
    raw_token = generate_login_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_magic_link_ttl_minutes)
    db.add(
        LoginToken(email=body.email, token_hash=hash_login_token(raw_token), expires_at=expires_at)
    )
    await db.commit()

    login_url = f"{settings.frontend_base_url}/auth/verify?token={raw_token}"
    if settings.smtp_host:
        send_magic_link_email(settings, body.email, login_url)
        logger.info("magic_link_sent", email=body.email)
        return RequestLinkResponse(detail="Check your email for a sign-in link.")

    logger.info("magic_link_dev_mode", email=body.email, login_url=login_url)
    return RequestLinkResponse(
        detail="SMTP isn't configured, so here's your dev-mode sign-in link directly.",
        dev_login_url=login_url,
    )


@router.get("/verify", response_model=UserOut)
async def verify(
    token: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    token_result = await db.execute(
        select(LoginToken).where(LoginToken.token_hash == hash_login_token(token))
    )
    login_token = token_result.scalar_one_or_none()
    now = datetime.now(UTC)
    if login_token is None or login_token.consumed_at is not None or login_token.expires_at < now:
        raise HTTPException(status_code=400, detail="This sign-in link is invalid or has expired.")

    login_token.consumed_at = now
    user_result = await db.execute(select(User).where(User.email == login_token.email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(email=login_token.email)
        db.add(user)
        await db.flush()
    await db.commit()

    response.set_cookie(
        settings.auth_cookie_name,
        create_session_cookie(user.id, settings),
        max_age=settings.auth_session_ttl_days * 86_400,
        httponly=True,
        samesite="lax",
        secure=settings.env != "development",
    )
    return user


@router.post("/logout")
async def logout(
    response: Response, settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, str]:
    response.delete_cookie(settings.auth_cookie_name)
    return {"detail": "Logged out."}


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
