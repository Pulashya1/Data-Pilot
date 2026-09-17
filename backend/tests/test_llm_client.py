"""Tests for `LLMClient` (MASTER_PROMPT.md §5.2, §5.8, §12 Phase 3): mock mode, retry/backoff/
fallback, rate limiting, caching, and the per-session call budget. Never calls a real LLM —
where a real code path is exercised, `litellm.acompletion` is monkeypatched instead.
"""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from litellm.exceptions import RateLimitError
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import LLMBudgetExceededError, LLMClient, LLMUnavailableError
from app.agent.tools.schemas import CodeRepair, ProposeTargetAndProblemType
from app.core.config import Settings
from app.models.session import FileType, SessionStatus, UploadSession
from tests.fakes import FakeRedis


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "llm_model": "gemini/gemini-2.0-flash",
        "llm_fallbacks": "groq/llama-3.1-8b-instant",
        "llm_rpm_limit": 100,
        "llm_tpm_limit": 200_000,
        "llm_max_calls_per_session": 5,
        "llm_cache_ttl_seconds": 60,
        "llm_retry_max_attempts": 2,
        "llm_retry_base_delay_seconds": 0.01,
    }
    base.update(overrides)
    return Settings(**base)


async def _make_session(db_session: AsyncSession) -> UploadSession:
    session = UploadSession(
        original_filename="data.csv",
        storage_key="k",
        file_type=FileType.CSV,
        size_bytes=10,
        status=SessionStatus.READY,
    )
    db_session.add(session)
    await db_session.flush()
    return session


def _understand_messages() -> list[dict[str, Any]]:
    payload = {
        "columns": [
            {
                "name": "target",
                "dtype": "int64",
                "semantic_type": "categorical",
                "unique_count": 2,
                "missing_pct": 0.0,
            }
        ]
    }
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": json.dumps(payload)},
    ]


class _FakeMessage:
    def __init__(self, tool_calls: list[Any] | None, content: str | None = None) -> None:
        self.tool_calls = tool_calls
        self.content = content


class _FakeToolCall:
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.function = _FakeFunction(name, json.dumps(arguments))


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeUsage:
    def __init__(self, prompt_tokens: int = 10, completion_tokens: int = 5) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeModelResponse:
    def __init__(self, message: _FakeMessage, model: str = "gemini/gemini-2.0-flash") -> None:
        self.choices = [_FakeChoice(message)]
        self.usage = _FakeUsage()
        self.model = model


def _tool_response(response_model: type[BaseModel], **fields: Any) -> _FakeModelResponse:
    tool_call = _FakeToolCall(response_model.__name__, fields)
    return _FakeModelResponse(_FakeMessage(tool_calls=[tool_call]))


async def test_mock_mode_never_touches_redis_or_budget(db_session: AsyncSession) -> None:
    settings = _settings(llm_model="mock")
    redis = FakeRedis()
    client = LLMClient(settings, redis)
    session = await _make_session(db_session)

    result = await client.complete_structured(
        _understand_messages(), ProposeTargetAndProblemType, db=db_session, session_id=session.id
    )

    assert isinstance(result, ProposeTargetAndProblemType)
    assert result.target_column == "target"
    assert result.problem_type == "binary_classification"
    assert redis.values == {}
    assert session.llm_calls_used == 0


async def test_mock_mode_code_repair_returns_a_no_op(db_session: AsyncSession) -> None:
    settings = _settings(llm_model="mock")
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    payload = {"code": "1/0", "error": "ZeroDivisionError"}
    messages = [{"role": "user", "content": json.dumps(payload)}]
    result = await client.complete_structured(
        messages, CodeRepair, db=db_session, session_id=session.id
    )
    assert isinstance(result, CodeRepair)
    assert result.code == "pass"


async def test_successful_call_updates_session_usage_and_caches(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings()
    redis = FakeRedis()
    client = LLMClient(settings, redis)
    session = await _make_session(db_session)

    mock_acompletion = AsyncMock(
        return_value=_tool_response(
            ProposeTargetAndProblemType,
            target_column="target",
            problem_type="binary_classification",
            reasoning="mocked",
            confidence="high",
        )
    )
    monkeypatch.setattr("app.agent.llm.litellm.acompletion", mock_acompletion)

    result = await client.complete_structured(
        _understand_messages(), ProposeTargetAndProblemType, db=db_session, session_id=session.id
    )

    assert result.target_column == "target"
    assert mock_acompletion.await_count == 1
    assert session.llm_calls_used == 1
    assert session.llm_tokens_used == 15
    assert session.llm_models_used == ["gemini/gemini-2.0-flash"]
    # `_FakeModelResponse` isn't a real litellm ModelResponse, so completion_cost can't price
    # it — degrades to 0.0 rather than raising (see LLMClient._completion_cost).
    assert session.llm_cost_used_usd == 0.0

    # A second, identically-shaped call should hit the Redis cache, not litellm again.
    # (`complete_structured` builds this exact tools payload internally — mirrored here so the
    # cache key matches.)
    await client.complete(
        _understand_messages(),
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "ProposeTargetAndProblemType",
                    "description": (ProposeTargetAndProblemType.__doc__ or "").strip(),
                    "parameters": ProposeTargetAndProblemType.model_json_schema(),
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "ProposeTargetAndProblemType"}},
        db=db_session,
        session_id=session.id,
    )
    assert mock_acompletion.await_count == 1


async def test_retries_then_succeeds_on_transient_error(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings()
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    mock_acompletion = AsyncMock(
        side_effect=[
            RateLimitError("rate limited", llm_provider="gemini", model="gemini-2.0-flash"),
            _tool_response(
                ProposeTargetAndProblemType,
                target_column="target",
                problem_type="binary_classification",
                reasoning="ok",
                confidence="high",
            ),
        ]
    )
    monkeypatch.setattr("app.agent.llm.litellm.acompletion", mock_acompletion)

    result = await client.complete_structured(
        _understand_messages(), ProposeTargetAndProblemType, db=db_session, session_id=session.id
    )
    assert result.target_column == "target"
    assert mock_acompletion.await_count == 2


async def test_falls_over_to_fallback_model_after_exhausting_primary(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(llm_retry_max_attempts=1)
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    calls: list[str] = []

    async def fake_acompletion(*, model: str, **_: Any) -> _FakeModelResponse:
        calls.append(model)
        if model == settings.llm_model:
            raise RateLimitError("rate limited", llm_provider="gemini", model=model)
        return _tool_response(
            ProposeTargetAndProblemType,
            target_column="target",
            problem_type="binary_classification",
            reasoning="ok",
            confidence="high",
        )

    monkeypatch.setattr("app.agent.llm.litellm.acompletion", fake_acompletion)

    result = await client.complete_structured(
        _understand_messages(), ProposeTargetAndProblemType, db=db_session, session_id=session.id
    )
    assert result.target_column == "target"
    assert calls == [settings.llm_model, "groq/llama-3.1-8b-instant"]


async def test_raises_when_every_model_is_exhausted(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(llm_retry_max_attempts=1)
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    async def always_fails(*, model: str, **_: Any) -> _FakeModelResponse:
        raise RateLimitError("rate limited", llm_provider="gemini", model=model)

    monkeypatch.setattr("app.agent.llm.litellm.acompletion", always_fails)

    with pytest.raises(LLMUnavailableError):
        await client.complete_structured(
            _understand_messages(),
            ProposeTargetAndProblemType,
            db=db_session,
            session_id=session.id,
        )


async def test_budget_exceeded_raises_before_calling_litellm(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(llm_max_calls_per_session=0)
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    mock_acompletion = AsyncMock()
    monkeypatch.setattr("app.agent.llm.litellm.acompletion", mock_acompletion)

    with pytest.raises(LLMBudgetExceededError):
        await client.complete_structured(
            _understand_messages(),
            ProposeTargetAndProblemType,
            db=db_session,
            session_id=session.id,
        )
    mock_acompletion.assert_not_awaited()


async def test_cost_budget_exceeded_raises_before_calling_litellm(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(llm_max_cost_per_session_usd=0.01)
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)
    session.llm_cost_used_usd = 0.02  # already over budget from earlier calls this session

    mock_acompletion = AsyncMock()
    monkeypatch.setattr("app.agent.llm.litellm.acompletion", mock_acompletion)

    with pytest.raises(LLMBudgetExceededError, match="max cost per session reached"):
        await client.complete_structured(
            _understand_messages(),
            ProposeTargetAndProblemType,
            db=db_session,
            session_id=session.id,
        )
    mock_acompletion.assert_not_awaited()


async def test_successful_call_accumulates_real_completion_cost(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings()
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    mock_acompletion = AsyncMock(
        return_value=_tool_response(
            ProposeTargetAndProblemType,
            target_column="target",
            problem_type="binary_classification",
            reasoning="mocked",
            confidence="high",
        )
    )
    monkeypatch.setattr("app.agent.llm.litellm.acompletion", mock_acompletion)
    monkeypatch.setattr("app.agent.llm.litellm.completion_cost", lambda **kwargs: 0.0123)

    await client.complete_structured(
        _understand_messages(), ProposeTargetAndProblemType, db=db_session, session_id=session.id
    )
    assert session.llm_cost_used_usd == pytest.approx(0.0123)

    # A second call accumulates on top of the first rather than overwriting it.
    monkeypatch.setattr("app.agent.llm.litellm.completion_cost", lambda **kwargs: 0.0050)
    await client.complete_structured(
        [{"role": "user", "content": "different prompt, so it's not a cache hit"}],
        ProposeTargetAndProblemType,
        db=db_session,
        session_id=session.id,
    )
    assert session.llm_cost_used_usd == pytest.approx(0.0173)


async def test_invalid_tool_arguments_are_retried_once_then_succeed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings()
    client = LLMClient(settings, FakeRedis())
    session = await _make_session(db_session)

    bad_args = {"problem_type": "not-a-real-type"}
    invalid = _FakeModelResponse(
        _FakeMessage(tool_calls=[_FakeToolCall("ProposeTargetAndProblemType", bad_args)])
    )
    valid = _tool_response(
        ProposeTargetAndProblemType,
        target_column=None,
        problem_type="clustering",
        reasoning="ok",
        confidence="low",
    )
    mock_acompletion = AsyncMock(side_effect=[invalid, valid])
    monkeypatch.setattr("app.agent.llm.litellm.acompletion", mock_acompletion)

    result = await client.complete_structured(
        _understand_messages(), ProposeTargetAndProblemType, db=db_session, session_id=session.id
    )
    assert result.problem_type == "clustering"
    assert mock_acompletion.await_count == 2
