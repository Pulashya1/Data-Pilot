"""Shared auth + ownership dependencies (MASTER_PROMPT.md §9, §12 Phase 8).

`get_current_user` reads the signed session cookie (`app/core/security.py`) set by
`POST /auth/verify`. `get_owned_session`/`get_ready_owned_session` build on it so every route
that takes a `session_id` path parameter enforces "users can access only their own sessions" in
one place, instead of each router re-implementing its own `_get_session_or_404` (as the
sessions/notebook/agent routers did pre-Phase-8) with no ownership check at all.

A session that exists but belongs to someone else 404s, the same as one that doesn't exist —
never 403 — so a session id can't be used to probe for existence.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.security import verify_session_cookie
from app.models.session import SessionStatus, UploadSession
from app.models.user import User


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    cookie_value = request.cookies.get(settings.auth_cookie_name)
    user_id = verify_session_cookie(cookie_value, settings) if cookie_value else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_owned_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UploadSession:
    session = await db.get(UploadSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def get_ready_owned_session(
    session: Annotated[UploadSession, Depends(get_owned_session)],
) -> UploadSession:
    if session.status != SessionStatus.READY or session.profile is None:
        raise HTTPException(status_code=409, detail="Session is not ready for analysis")
    return session
