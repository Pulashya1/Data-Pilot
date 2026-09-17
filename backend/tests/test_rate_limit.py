"""Unit tests for the fixed-window API rate limiter (MASTER_PROMPT.md §9, §12 Phase 8)."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import Settings
from app.core.rate_limit import rate_limit
from tests.fakes import FakeRedis


def _request(ip: str = "1.2.3.4") -> Request:
    return Request({"type": "http", "client": (ip, 12345), "headers": []})


async def test_allows_requests_under_the_limit() -> None:
    settings = Settings(api_rate_limit_per_minute=2)
    redis = FakeRedis()
    await rate_limit(_request(), settings, redis)
    await rate_limit(_request(), settings, redis)


async def test_blocks_requests_over_the_limit() -> None:
    settings = Settings(api_rate_limit_per_minute=1)
    redis = FakeRedis()
    await rate_limit(_request(), settings, redis)
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit(_request(), settings, redis)
    assert exc_info.value.status_code == 429


async def test_disabled_when_limit_is_zero() -> None:
    settings = Settings(api_rate_limit_per_minute=0)
    redis = FakeRedis()
    for _ in range(10):
        await rate_limit(_request(), settings, redis)


async def test_separate_ips_get_separate_budgets() -> None:
    settings = Settings(api_rate_limit_per_minute=1)
    redis = FakeRedis()
    await rate_limit(_request("1.1.1.1"), settings, redis)
    await rate_limit(_request("2.2.2.2"), settings, redis)
