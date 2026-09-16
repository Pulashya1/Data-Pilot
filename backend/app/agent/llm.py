"""LiteLLM-backed LLM client (MASTER_PROMPT.md §2, §5.2, §5.8, §12 Phase 3).

The *only* module that imports `litellm` or knows a provider's name (CLAUDE.md: "Never call a
provider SDK directly elsewhere, never hardcode model names"). Two call shapes:

- `complete`: a raw chat completion, optionally with tools — retried with backoff across
  `[llm_model, *llm_fallbacks]`, rate-limited and cached in Redis, counted against the
  per-session call budget.
- `complete_structured`: forces a single tool call bound to a Pydantic model, validates the
  arguments, and on a validation error sends the error back to the model and retries once
  (§5.2). This is the only entry point every agent node actually uses.

`LLM_MODEL=mock` (§5.8 "Dev mode") short-circuits `complete_structured` before any of the
above — no network, no Redis, no budget spent — via a small deterministic heuristic shared with
the real-LLM graceful-degradation fallback in `app/agent/nodes.py` (`app/agent/heuristics.py`).
"""

import asyncio
import hashlib
import json
import random
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any, TypeVar, cast

import litellm
from litellm.exceptions import APIConnectionError, InternalServerError, RateLimitError, Timeout
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import heuristics
from app.agent.tools.schemas import CodeRepair, ProposeTargetAndProblemType
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis import RedisLike, get_redis_client
from app.models.session import UploadSession

logger = get_logger(__name__)

_RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, Timeout, InternalServerError)
T = TypeVar("T", bound=BaseModel)

StatusCallback = Callable[[str], Awaitable[None]] | None


class LLMUnavailableError(RuntimeError):
    """Every configured model (primary + fallbacks) failed after retries."""


class LLMBudgetExceededError(RuntimeError):
    """The session has hit `LLM_MAX_CALLS_PER_SESSION`."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session {session_id} has exceeded its LLM call budget.")
        self.session_id = session_id


class ToolCallOut(BaseModel):
    name: str
    arguments: dict[str, Any]


class LLMUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class LLMResponse(BaseModel):
    content: str | None
    tool_calls: list[ToolCallOut]
    model: str
    usage: LLMUsage


class LLMClient:
    def __init__(self, settings: Settings, redis_client: RedisLike) -> None:
        self._settings = settings
        self._redis = redis_client
        self.is_mock = settings.llm_model == "mock"

    # -- structured calls (the only interface agent nodes use) --------------------------------

    async def complete_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        *,
        db: AsyncSession,
        session_id: str,
        status_callback: StatusCallback = None,
    ) -> T:
        if self.is_mock:
            return self._mock_complete_structured(messages, response_model)

        tool_name = response_model.__name__
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": (response_model.__doc__ or "").strip(),
                    "parameters": response_model.model_json_schema(),
                },
            }
        ]
        tool_choice = {"type": "function", "function": {"name": tool_name}}

        response = await self.complete(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            db=db,
            session_id=session_id,
            status_callback=status_callback,
        )
        parsed, error = self._extract_tool_args(response, tool_name, response_model)
        if parsed is not None:
            return parsed

        # §5.2: send the validation error back to the model and retry once.
        retry_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    f"Your previous response's arguments for `{tool_name}` were invalid: "
                    f"{error}. Call `{tool_name}` again with valid arguments matching its "
                    "JSON schema exactly."
                ),
            },
        ]
        response = await self.complete(
            retry_messages,
            tools=tools,
            tool_choice=tool_choice,
            db=db,
            session_id=session_id,
            status_callback=status_callback,
        )
        parsed, error = self._extract_tool_args(response, tool_name, response_model)
        if parsed is not None:
            return parsed
        raise LLMUnavailableError(
            f"Model did not return valid arguments for {tool_name} after one retry: {error}"
        )

    def _mock_complete_structured(
        self, messages: list[dict[str, Any]], response_model: type[T]
    ) -> T:
        if response_model is ProposeTargetAndProblemType:
            payload = json.loads(messages[-1]["content"])
            result = heuristics.propose_target_and_problem_type(payload["columns"])
            return cast(T, result)
        if response_model is CodeRepair:
            repair = CodeRepair(
                code="pass",
                explanation="mock repair (LLM_MODEL=mock): replaced the failing cell with a no-op.",
            )
            return cast(T, repair)
        raise NotImplementedError(f"mock LLM has no handler for {response_model.__name__}")

    @staticmethod
    def _extract_tool_args(
        response: LLMResponse, tool_name: str, response_model: type[T]
    ) -> tuple[T | None, str | None]:
        matching = [tc for tc in response.tool_calls if tc.name == tool_name]
        if not matching:
            return None, "the model did not call the expected tool"
        try:
            return response_model.model_validate(matching[0].arguments), None
        except ValidationError as exc:
            return None, str(exc)

    # -- raw calls: retry, fallback, rate limit, cache, budget ---------------------------------

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        db: AsyncSession,
        session_id: str,
        status_callback: StatusCallback = None,
    ) -> LLMResponse:
        if self.is_mock:
            raise NotImplementedError("LLM_MODEL=mock only supports complete_structured().")

        session = await db.get(UploadSession, session_id)
        if session is None:
            raise ValueError(f"Unknown session {session_id!r}")
        if session.llm_calls_used >= self._settings.llm_max_calls_per_session:
            raise LLMBudgetExceededError(session_id)

        models = [self._settings.llm_model, *self._fallback_models()]
        cache_key = self._cache_key(models[0], messages, tools)
        cached = await self._redis.get(cache_key)
        if cached:
            return LLMResponse.model_validate_json(cached)

        estimated_tokens = max(len(json.dumps(messages)) // 4, 1)
        last_error: Exception | None = None

        for model_index, model in enumerate(models):
            provider = model.split("/", 1)[0]
            for attempt in range(self._settings.llm_retry_max_attempts):
                await self._wait_for_capacity(provider, estimated_tokens, status_callback)
                if status_callback is not None:
                    await status_callback("calling")
                start = time.monotonic()
                try:
                    raw = await litellm.acompletion(
                        model=model, messages=messages, tools=tools, tool_choice=tool_choice
                    )
                except _RETRYABLE_ERRORS as exc:
                    last_error = exc
                    logger.warning(
                        "llm_call_retry",
                        model=model,
                        attempt=attempt,
                        latency_ms=(time.monotonic() - start) * 1000,
                        error=str(exc),
                    )
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue

                result = self._parse_response(raw, model)
                await self._redis.set(
                    cache_key, result.model_dump_json(), ex=self._settings.llm_cache_ttl_seconds
                )
                self._record_usage(session, model, result.usage)
                await db.flush()
                logger.info(
                    "llm_call",
                    model=model,
                    latency_ms=(time.monotonic() - start) * 1000,
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                    retries=attempt,
                    fallback_used=model_index > 0,
                )
                return result
            logger.warning("llm_model_exhausted", model=model, error=str(last_error))

        logger.error("llm_all_models_failed", error=str(last_error))
        raise LLMUnavailableError(str(last_error) if last_error else "no models configured")

    def _fallback_models(self) -> list[str]:
        return [m.strip() for m in self._settings.llm_fallbacks.split(",") if m.strip()]

    def _backoff_delay(self, attempt: int) -> float:
        base: float = self._settings.llm_retry_base_delay_seconds
        delay: float = base * (2**attempt) + random.uniform(0, 0.5)
        return delay

    @staticmethod
    def _record_usage(session: UploadSession, model: str, usage: LLMUsage) -> None:
        session.llm_calls_used += 1
        session.llm_tokens_used += usage.prompt_tokens + usage.completion_tokens
        models_used = set(session.llm_models_used or [])
        models_used.add(model)
        session.llm_models_used = sorted(models_used)

    async def _wait_for_capacity(
        self, provider: str, estimated_tokens: int, status_callback: StatusCallback
    ) -> None:
        warned = False
        while True:
            window = int(time.time() // 60)
            rpm_key = f"llm:rl:{provider}:rpm:{window}"
            tpm_key = f"llm:rl:{provider}:tpm:{window}"
            calls = int((await self._redis.get(rpm_key)) or 0)
            tokens = int((await self._redis.get(tpm_key)) or 0)
            if calls < self._settings.llm_rpm_limit and (
                tokens + estimated_tokens <= self._settings.llm_tpm_limit
            ):
                await self._redis.incrby(rpm_key, 1)
                await self._redis.expire(rpm_key, 120)
                await self._redis.incrby(tpm_key, estimated_tokens)
                await self._redis.expire(tpm_key, 120)
                return
            if status_callback is not None and not warned:
                await status_callback("waiting_for_capacity")
                warned = True
            await asyncio.sleep(1.0)

    @staticmethod
    def _cache_key(
        model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> str:
        payload = json.dumps(
            {"model": model, "messages": messages, "tools": tools}, sort_keys=True, default=str
        )
        return "llm:cache:" + hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _parse_response(raw: Any, model: str) -> LLMResponse:
        message = raw.choices[0].message
        tool_calls = []
        for tc in message.tool_calls or []:
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(ToolCallOut(name=tc.function.name, arguments=arguments))
        usage = raw.usage
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            model=getattr(raw, "model", None) or model,
            usage=LLMUsage(
                prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens
            ),
        )


@lru_cache
def get_llm_client() -> LLMClient:
    # redis-py's real client structurally satisfies `RedisLike` (it accepts a superset of the
    # arguments we ever pass) but its signatures are wider than the narrow Protocol declares.
    return LLMClient(get_settings(), cast(RedisLike, get_redis_client()))
