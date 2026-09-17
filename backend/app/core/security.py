"""Stateless session-cookie signing + magic-link token hashing (MASTER_PROMPT.md §9, §12
Phase 8).

No JWT/itsdangerous dependency — MASTER_PROMPT.md §2/§13 says not to add a library outside the
spec's stack without asking, and a signed session cookie doesn't need one: it's just
`"<user_id>.<expires_at_epoch>.<hmac_hex>"`, signed with `Settings.auth_secret_key` via stdlib
`hmac`/`hashlib`. `hmac.compare_digest` makes verification constant-time. This intentionally
carries no server-side revocation list — logging out just deletes the cookie client-side; a
stolen cookie stays valid until `auth_session_ttl_days` expires it, which is an accepted
trade-off for "simple auth" (MASTER_PROMPT.md §9) rather than a session-store table.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import Settings


def generate_login_token() -> str:
    """A raw, one-time magic-link token — mailed to the user, never stored (see
    `hash_login_token`)."""
    return secrets.token_urlsafe(32)


def hash_login_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_cookie(user_id: str, settings: Settings) -> str:
    expires_at = int(
        (datetime.now(UTC) + timedelta(days=settings.auth_session_ttl_days)).timestamp()
    )
    payload = f"{user_id}.{expires_at}"
    return f"{payload}.{_sign(payload, settings.auth_secret_key)}"


def verify_session_cookie(cookie_value: str, settings: Settings) -> str | None:
    """Returns the `user_id` the cookie was signed for, or `None` if it's missing, malformed,
    forged, or expired."""
    parts = cookie_value.split(".")
    if len(parts) != 3:
        return None
    user_id, expires_at_raw, signature = parts
    payload = f"{user_id}.{expires_at_raw}"
    if not hmac.compare_digest(_sign(payload, settings.auth_secret_key), signature):
        return None
    try:
        expires_at = int(expires_at_raw)
    except ValueError:
        return None
    if datetime.now(UTC).timestamp() > expires_at:
        return None
    return user_id
