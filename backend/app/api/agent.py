"""Agent run + SSE streaming + decision + Q&A chat endpoints (MASTER_PROMPT.md §7, §8,
§12 Phase 3/4/7)."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.decisions import InvalidAnswerError, get_decision, validate_answer
from app.agent.deps import NodeDeps
from app.agent.events import SessionEventBus, get_event_bus
from app.agent.llm import LLMClient, get_llm_client
from app.agent.qa import answer_question
from app.agent.runner import (
    AgentAlreadyRunningError,
    AgentNotWaitingError,
    AgentRunner,
    SessionNotReadyError,
    UnknownSessionError,
    get_agent_runner,
)
from app.api.deps import get_owned_session, get_ready_owned_session
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.core.storage import StorageBackend, get_storage_backend
from app.execution.backend import ExecutionBackend
from app.execution.kernel_manager import (
    KernelManager,
    get_execution_backend,
    get_kernel_manager,
)
from app.models.chat import ChatMessage
from app.models.decision import Decision, DecisionKind
from app.models.session import AgentStatus, UploadSession
from app.schemas.chat import AskQuestionRequest, ChatMessageOut
from app.schemas.decision import AnswerDecisionRequest, DecisionOut, EditPlanRequest
from app.schemas.events import AgentStatusEvent
from app.schemas.session import UsageOut

router = APIRouter(tags=["agent"], dependencies=[Depends(rate_limit)])

_KEEPALIVE_SECONDS = 15.0


async def _answer_decision(
    session: UploadSession,
    decision: Decision,
    raw_answer: str,
    db: AsyncSession,
    runner: AgentRunner,
) -> Decision:
    """Shared by `POST /decisions/{id}` and `POST /plan` (MASTER_PROMPT.md §8): validates the
    answer, writes it to the (still-paused) `Decision` row, then resumes the graph. The DB write
    happens *before* `runner.resume` so the resumed node finds an already-answered decision —
    see `app.agent.decisions`'s module docstring for why that ordering matters."""
    if session.agent_status != AgentStatus.WAITING_DECISION or decision.selected_option is not None:
        raise HTTPException(
            status_code=409, detail="This decision isn't currently awaiting an answer."
        )
    try:
        answer = validate_answer(decision, raw_answer)
    except InvalidAnswerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    decision.selected_option = answer
    decision.auto_decided = False
    await db.commit()

    try:
        await runner.resume(session.id, answer)
    except AgentNotWaitingError as exc:
        raise HTTPException(
            status_code=409, detail="The agent is not waiting on a decision."
        ) from exc
    return decision


@router.post("/sessions/{session_id}/agent/start", status_code=202)
async def start_agent(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    runner: Annotated[AgentRunner, Depends(get_agent_runner)],
) -> dict[str, str]:
    try:
        await runner.start(session.id)
    except UnknownSessionError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except SessionNotReadyError as exc:
        raise HTTPException(status_code=409, detail="Session is not ready for analysis") from exc
    except AgentAlreadyRunningError as exc:
        raise HTTPException(
            status_code=409, detail="The agent is already running for this session"
        ) from exc
    return {"status": "started"}


@router.get("/sessions/{session_id}/stream")
async def stream_agent(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    request: Request,
    bus: Annotated[SessionEventBus, Depends(get_event_bus)],
) -> StreamingResponse:
    session_id = session.id

    async def event_source() -> AsyncGenerator[str]:
        subscription = bus.subscribe(session_id)
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(
                        subscription.__anext__(), timeout=_KEEPALIVE_SECONDS
                    )
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(event.model_dump())}\n\n"
                if isinstance(event, AgentStatusEvent) and event.status in (
                    "done",
                    "error",
                    "waiting_decision",
                ):
                    return
        finally:
            await subscription.aclose()

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/decisions", response_model=list[DecisionOut])
async def list_decisions(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DecisionOut]:
    result = await db.execute(
        select(Decision)
        .where(Decision.session_id == session.id)
        .order_by(Decision.created_at.asc())
    )
    return [DecisionOut.from_decision(d) for d in result.scalars().all()]


@router.post("/sessions/{session_id}/decisions/{decision_id}", response_model=DecisionOut)
async def answer_decision(
    decision_id: str,
    body: AnswerDecisionRequest,
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    runner: Annotated[AgentRunner, Depends(get_agent_runner)],
) -> DecisionOut:
    decision = await db.get(Decision, decision_id)
    if decision is None or decision.session_id != session.id:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision = await _answer_decision(session, decision, body.selected_option, db, runner)
    return DecisionOut.from_decision(decision)


@router.post("/sessions/{session_id}/plan", response_model=DecisionOut)
async def edit_plan(
    body: EditPlanRequest,
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    runner: Annotated[AgentRunner, Depends(get_agent_runner)],
) -> DecisionOut:
    """Structured plan-editing endpoint (MASTER_PROMPT.md §8): a nicer body than the generic
    `/decisions/{id}` answer for the one decision kind whose answer is itself a list. Answers
    whichever `plan_approval` decision is currently pending for this session."""
    decision = await get_decision(db, session.id, DecisionKind.PLAN_APPROVAL)
    if decision is None:
        raise HTTPException(status_code=409, detail="No plan is awaiting approval yet.")

    decision = await _answer_decision(session, decision, ",".join(body.steps), db, runner)
    return DecisionOut.from_decision(decision)


@router.get("/sessions/{session_id}/usage", response_model=UsageOut)
async def get_usage(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsageOut:
    return UsageOut(
        calls_used=session.llm_calls_used,
        calls_budget=settings.llm_max_calls_per_session,
        tokens_used=session.llm_tokens_used,
        cost_used_usd=session.llm_cost_used_usd,
        cost_budget_usd=settings.llm_max_cost_per_session_usd,
        models_used=session.llm_models_used or [],
    )


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageOut, status_code=201)
async def post_message(
    body: AskQuestionRequest,
    session: Annotated[UploadSession, Depends(get_ready_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
    backend: Annotated[ExecutionBackend, Depends(get_execution_backend)],
    kernel_manager: Annotated[KernelManager, Depends(get_kernel_manager)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    bus: Annotated[SessionEventBus, Depends(get_event_bus)],
) -> ChatMessage:
    """MASTER_PROMPT.md §5.6, §8: ask a question about the dataset, a chart, an insight, a
    decision, or a specific cell (`@cell-<position>`). Synchronous — see `app.agent.qa`'s
    module docstring for why this isn't routed through the LangGraph agent run."""
    deps = NodeDeps(
        db=db,
        storage=storage,
        backend=backend,
        kernel_manager=kernel_manager,
        settings=settings,
        llm_client=llm_client,
        bus=bus,
    )
    return await answer_question(deps, session, body.content)
