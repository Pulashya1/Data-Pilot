"""Unit tests for the signed session-cookie helpers (MASTER_PROMPT.md §9, §12 Phase 8)."""

from app.core.config import Settings
from app.core.security import (
    create_session_cookie,
    generate_login_token,
    hash_login_token,
    verify_session_cookie,
)


def _settings(**overrides: object) -> Settings:
    overrides.setdefault("auth_secret_key", "test-secret")
    return Settings(**overrides)  # type: ignore[arg-type]


def test_generate_login_token_is_unique_and_reasonably_long() -> None:
    tokens = {generate_login_token() for _ in range(20)}
    assert len(tokens) == 20
    assert all(len(t) >= 32 for t in tokens)


def test_hash_login_token_is_deterministic_and_not_reversible() -> None:
    token = generate_login_token()
    assert hash_login_token(token) == hash_login_token(token)
    assert hash_login_token(token) != token


def test_session_cookie_round_trips() -> None:
    settings = _settings()
    cookie = create_session_cookie("user-123", settings)
    assert verify_session_cookie(cookie, settings) == "user-123"


def test_session_cookie_rejects_a_tampered_signature() -> None:
    settings = _settings()
    cookie = create_session_cookie("user-123", settings)
    user_id, expires_at, _signature = cookie.split(".")
    tampered = f"{user_id}.{expires_at}.deadbeef"
    assert verify_session_cookie(tampered, settings) is None


def test_session_cookie_rejects_a_different_secret() -> None:
    cookie = create_session_cookie("user-123", _settings(auth_secret_key="secret-a"))
    assert verify_session_cookie(cookie, _settings(auth_secret_key="secret-b")) is None


def test_session_cookie_rejects_an_expired_cookie() -> None:
    settings = _settings(auth_session_ttl_days=0)
    cookie = create_session_cookie("user-123", settings)
    assert verify_session_cookie(cookie, settings) is None


def test_verify_session_cookie_rejects_malformed_values() -> None:
    settings = _settings()
    assert verify_session_cookie("not-a-valid-cookie", settings) is None
    assert verify_session_cookie("", settings) is None
