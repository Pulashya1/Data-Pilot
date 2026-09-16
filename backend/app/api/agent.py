"""Agent run + SSE streaming + decision endpoints (MASTER_PROMPT.md §7, §8, §12 Phase 3/4)."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.decisions import InvalidAnswerError, get_decision, validate_answer
from app.agent.events import SessionEventBus, get_event_bus
from app.agent.runner import (
    AgentAlreadyRunningError,
    AgentNotWaitingError,
    AgentRunner,
    SessionNotReadyError,
    UnknownSessionError,
    get_agent_runner,
)
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.models.decision import Decision, DecisionKind
from app.models.session import AgentStatus, UploadSession
from app.schemas.decision import AnswerDecisionRequest, DecisionOut, EditPlanRequest
from app.schemas.events import AgentStatusEvent
from app.schemas.session import UsageOut

router = APIRouter(tags=["agent"])

_KEEPALIVE_SECONDS = 15.0


async def _get_session_or_404(session_id: str, db: AsyncSession) -> UploadSession:
    session = await db.get(UploadSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


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
    session_id: str, runner: Annotated[AgentRunner, Depends(get_agent_runner)]
) -> dict[str, str]:
    try:
        await runner.start(session_id)
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
    session_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    bus: Annotated[SessionEventBus, Depends(get_event_bus)],
) -> StreamingResponse:
    await _get_session_or_404(session_id, db)

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
    session_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[DecisionOut]:
    await _get_session_or_404(session_id, db)
    result = await db.execute(
        select(Decision)
        .where(Decision.session_id == session_id)
        .order_by(Decision.created_at.asc())
    )
    return [DecisionOut.from_decision(d) for d in result.scalars().all()]


@router.post("/sessions/{session_id}/decisions/{decision_id}", response_model=DecisionOut)
async def answer_decision(
    session_id: str,
    decision_id: str,
    body: AnswerDecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    runner: Annotated[AgentRunner, Depends(get_agent_runner)],
) -> DecisionOut:
    session = await _get_session_or_404(session_id, db)
    decision = await db.get(Decision, decision_id)
    if decision is None or decision.session_id != session_id:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision = await _answer_decision(session, decision, body.selected_option, db, runner)
    return DecisionOut.from_decision(decision)


@router.post("/sessions/{session_id}/plan", response_model=DecisionOut)
async def edit_plan(
    session_id: str,
    body: EditPlanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    runner: Annotated[AgentRunner, Depends(get_agent_runner)],
) -> DecisionOut:
    """Structured plan-editing endpoint (MASTER_PROMPT.md §8): a nicer body than the generic
    `/decisions/{id}` answer for the one decision kind whose answer is itself a list. Answers
    whichever `plan_approval` decision is currently pending for this session."""
    session = await _get_session_or_404(session_id, db)
    decision = await get_decision(db, session_id, DecisionKind.PLAN_APPROVAL)
    if decision is None:
        raise HTTPException(status_code=409, detail="No plan is awaiting approval yet.")

    decision = await _answer_decision(session, decision, ",".join(body.steps), db, runner)
    return DecisionOut.from_decision(decision)


@router.get("/sessions/{session_id}/usage", response_model=UsageOut)
async def get_usage(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsageOut:
    session = await _get_session_or_404(session_id, db)
    return UsageOut(
        calls_used=session.llm_calls_used,
        calls_budget=settings.llm_max_calls_per_session,
        tokens_used=session.llm_tokens_used,
        models_used=session.llm_models_used or [],
    )
