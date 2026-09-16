"""Background agent-run orchestration (MASTER_PROMPT.md §12 Phase 3/4).

`AgentRunner.start` spawns a detached `asyncio.Task` per session running the compiled graph
(`app/agent/graph.py`) to completion or the first pause; nodes publish their own
`SessionEventBus` events as they go (see `app/agent/nodes.py`), so this just has to drive the
stream. `AgentRunner.resume` spawns the same kind of task, but re-enters the graph with
`Command(resume=answer)` against the same checkpointed thread (`thread_id=session_id`) instead
of a fresh initial state — see `app/agent/decisions.py` for how a paused node's `interrupt()`
call receives that answer.

A `stream_mode="updates"` chunk with an `"__interrupt__"` key means a node called `interrupt()`
and the graph is now paused, checkpointed, and waiting — not an error. The node itself already
recorded `agent_status=waiting_decision` and published the matching events (see
`app.agent.decisions.resolve_decision`) before pausing, so `_run` just has to stop driving the
stream and let the task end quietly.

The top-level `except Exception` in `_run` *is* justified — a background-task boundary, not a
masked bug: an exception raised inside a detached `asyncio.Task` otherwise vanishes silently
instead of ever reaching a caller, so this is the only place that can turn it into
`agent_status=error` and an `ErrorEvent`. Every narrower, expected failure (LLM unavailable,
budget exceeded) is already caught inside the nodes themselves.
"""

import asyncio
from functools import lru_cache

from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import deps as deps_module
from app.agent.events import SessionEventBus, get_event_bus
from app.agent.graph import compile_graph
from app.agent.llm import LLMClient, get_llm_client
from app.agent.state import AgentState
from app.core.config import Settings, get_settings
from app.core.db import async_session_maker as default_session_maker
from app.core.logging import get_logger
from app.core.storage import StorageBackend, get_storage_backend
from app.execution.backend import ExecutionBackend
from app.execution.kernel_manager import KernelManager, get_execution_backend, get_kernel_manager
from app.models.session import AgentStatus, SessionStatus, UploadSession
from app.schemas.events import AgentStatusEvent, ErrorEvent

logger = get_logger(__name__)


class AgentAlreadyRunningError(RuntimeError):
    pass


class UnknownSessionError(RuntimeError):
    pass


class SessionNotReadyError(RuntimeError):
    pass


class AgentNotWaitingError(RuntimeError):
    pass


class AgentRunner:
    def __init__(
        self,
        storage: StorageBackend,
        backend: ExecutionBackend,
        kernel_manager: KernelManager,
        llm_client: LLMClient,
        bus: SessionEventBus,
        settings: Settings,
        session_maker: async_sessionmaker[AsyncSession] = default_session_maker,
    ) -> None:
        # A background task can't use `Depends(get_db)` (there's no request), so it needs its
        # own session factory — injectable (like `storage`/`backend` above) so tests can point
        # it at the test database's engine instead of the app's real one.
        self._storage = storage
        self._backend = backend
        self._kernel_manager = kernel_manager
        self._llm_client = llm_client
        self._bus = bus
        self._settings = settings
        self._session_maker = session_maker
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self, session_id: str) -> None:
        async with self._session_maker() as db:
            session = await db.get(UploadSession, session_id)
            if session is None:
                raise UnknownSessionError(session_id)
            if session.status != SessionStatus.READY:
                raise SessionNotReadyError(session_id)
            if session.agent_status == AgentStatus.RUNNING:
                raise AgentAlreadyRunningError(session_id)
            session.agent_status = AgentStatus.RUNNING
            session.agent_error_message = None
            await db.commit()

        initial_state: AgentState = {
            "session_id": session_id,
            "problem_type": None,
            "target_column": None,
            "plan": [],
            "step_index": 0,
        }
        self._tasks[session_id] = asyncio.create_task(self._run(session_id, initial_state))

    async def resume(self, session_id: str, answer: str) -> None:
        """Re-enters the paused graph with the user's decision answer (MASTER_PROMPT.md §5.1,
        §12 Phase 4). The API endpoint that calls this (`app/api/agent.py`) has already written
        `answer` onto the pending `Decision` row — see `app.agent.decisions` for why the node
        itself doesn't need to re-read it off the `Command`."""
        async with self._session_maker() as db:
            session = await db.get(UploadSession, session_id)
            if session is None:
                raise UnknownSessionError(session_id)
            if session.agent_status != AgentStatus.WAITING_DECISION:
                raise AgentNotWaitingError(session_id)
            session.agent_status = AgentStatus.RUNNING
            await db.commit()

        self._tasks[session_id] = asyncio.create_task(self._run(session_id, Command(resume=answer)))

    async def _run(self, session_id: str, graph_input: AgentState | Command) -> None:
        try:
            async with self._session_maker() as db:
                deps_module.register(
                    session_id,
                    deps_module.NodeDeps(
                        db=db,
                        storage=self._storage,
                        backend=self._backend,
                        kernel_manager=self._kernel_manager,
                        settings=self._settings,
                        llm_client=self._llm_client,
                        bus=self._bus,
                    ),
                )
                try:
                    graph = compile_graph()
                    config = {"configurable": {"thread_id": session_id}}
                    stream = graph.astream(graph_input, config, stream_mode="updates")
                    async for update in stream:
                        if "__interrupt__" in update:
                            # Paused, not failed — the node already recorded
                            # agent_status=waiting_decision and published its own events
                            # (app.agent.decisions.resolve_decision). Nothing left to drive.
                            return
                finally:
                    deps_module.unregister(session_id)
        except Exception as exc:  # noqa: BLE001 - background-task boundary, see module docstring
            logger.error("agent_run_failed", session_id=session_id, error=str(exc), exc_info=True)
            async with self._session_maker() as db:
                session = await db.get(UploadSession, session_id)
                if session is not None:
                    session.agent_status = AgentStatus.ERROR
                    session.agent_error_message = str(exc)
                    await db.commit()
            await self._bus.publish(session_id, ErrorEvent(message=str(exc)))
            await self._bus.publish(
                session_id, AgentStatusEvent(status="error", error_message=str(exc))
            )
        finally:
            self._tasks.pop(session_id, None)


@lru_cache
def get_agent_runner() -> AgentRunner:
    return AgentRunner(
        get_storage_backend(),
        get_execution_backend(),
        get_kernel_manager(),
        get_llm_client(),
        get_event_bus(),
        get_settings(),
    )
