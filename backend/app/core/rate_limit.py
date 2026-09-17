"""Fixed-window per-client API rate limiting (MASTER_PROMPT.md §9: "Rate-limit API calls per
user, in addition to the LLM rate limiting in §5.8") — independent of `LLMClient`'s own
token-bucket rate limiter (`app/agent/llm.py`), which only guards outbound LLM-provider calls.

Keyed by client IP rather than user id, so it also covers the pre-auth `POST /auth/request-link`
endpoint — arguably the one most worth protecting from abuse, since each call can trigger a real
email send. A fixed one-minute window in Redis (reusing `app.core.redis.RedisLike`, the same
narrow protocol `LLMClient` depends on, so tests inject the same `FakeRedis`) is simple and
sufficient here; it doesn't need the token-bucket smoothing `LLMClient` uses for its own,
per-provider-plan limits.
"""

import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.redis import RedisLike, get_redis_client

_WINDOW_SECONDS = 60


async def rate_limit(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[RedisLike, Depends(get_redis_client)],
) -> None:
    limit = settings.api_rate_limit_per_minute
    if limit <= 0:
        return
    client_ip = request.client.host if request.client else "unknown"
    window = int(time.time() // _WINDOW_SECONDS)
    key = f"apiratelimit:{client_ip}:{window}"
    count = await redis_client.incrby(key)
    if count == 1:
        await redis_client.expire(key, _WINDOW_SECONDS)
    if count > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
