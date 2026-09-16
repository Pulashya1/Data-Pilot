"""Redis client (LLM rate limiting and response cache, MASTER_PROMPT.md §5.8, §12 Phase 3)."""

from functools import lru_cache
from typing import Protocol

from redis.asyncio import Redis

from app.core.config import get_settings


class RedisLike(Protocol):
    """The narrow slice of the redis-py async API `LLMClient` needs — lets tests inject an
    in-memory fake (`tests/fakes.py::FakeRedis`) instead of a real Redis server."""

    async def get(self, name: str) -> bytes | str | None: ...

    async def set(self, name: str, value: str, ex: int | None = None) -> object: ...

    async def incrby(self, name: str, amount: int = 1) -> int: ...

    async def expire(self, name: str, seconds: int) -> object: ...


@lru_cache
def get_redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url)  # type: ignore[no-any-return]
