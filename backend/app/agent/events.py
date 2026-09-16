"""In-process SSE fan-out for agent runs (MASTER_PROMPT.md §7, §8, §12 Phase 3).

Same in-process-dict pub/sub style as `KernelManager`'s handle tracking
(`app/execution/kernel_manager.py`) rather than Redis — one backend process, matches the
existing Phase 2 architecture. `app/api/agent.py`'s `GET /sessions/{id}/stream` subscribes;
agent nodes (`app/agent/nodes.py`) publish.
"""

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator
from functools import lru_cache

from app.schemas.events import AgentEvent


class SessionEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[AgentEvent]]] = defaultdict(list)

    async def publish(self, session_id: str, event: AgentEvent) -> None:
        for queue in list(self._subscribers.get(session_id, [])):
            await queue.put(event)

    async def subscribe(self, session_id: str) -> AsyncGenerator[AgentEvent]:
        """Yields events indefinitely; the caller (`app/api/agent.py`) is responsible for
        keep-alives and stopping once a terminal event arrives or the client disconnects."""
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[session_id].remove(queue)
            if not self._subscribers[session_id]:
                self._subscribers.pop(session_id, None)


@lru_cache
def get_event_bus() -> SessionEventBus:
    return SessionEventBus()
