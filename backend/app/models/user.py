"""ORM models for email-magic-link auth (MASTER_PROMPT.md §9, §12 Phase 8).

Two tables: `User` (one row per email, created lazily on first successful login) and
`LoginToken` (one-time-use magic-link tokens). The session cookie itself is *not* backed by a
DB row — it's a stateless HMAC-signed value (`app/core/security.py`) carrying `user_id` and an
expiry, so verifying it on every request costs one `db.get(User, ...)` and no extra table.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginToken(Base):
    """A single magic-link token. `token_hash` (sha256 hex of the raw token mailed to the
    user) is stored, never the raw token itself — mirrors not storing plaintext passwords,
    and means a DB read alone can't be replayed as a valid login."""

    __tablename__ = "login_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Owning FK added to `UploadSession` in app/models/session.py rather than here, to keep the
# forward reference simple (SQLAlchemy resolves string FKs by table name, not import order) —
# `ForeignKey("users.id")` there requires this module to have been imported at least once
# before `Base.metadata.create_all`/Alembic runs, which app/models/__init__.py guarantees.
__all__ = ["LoginToken", "User"]
