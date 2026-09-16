"""Session-keyed kernel orchestration on top of an `ExecutionBackend` (MASTER_PROMPT.md §3, §12).

Kept deliberately unaware of the database, storage, and notebook models: callers pass an
`on_start` hook that runs whenever a *new* container had to be started for a session — both
for the session's first kernel and for crash recovery (§3: "kernel rebuilt by re-executing
the notebook's accepted cells"). The hook typically seeds the dataset file and replays prior
cells; `KernelManager` itself only tracks liveness and idles kernels out.
"""

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal

from app.core.config import get_settings
from app.execution.backend import ExecutionBackend, KernelHandle
from app.execution.docker_backend import DockerJupyterBackend
from app.schemas.execution import ExecutionResult

OnStartHook = Callable[[KernelHandle], Awaitable[None]]
KernelStatus = Literal["stopped", "running"]


class KernelManager:
    def __init__(
        self,
        backend: ExecutionBackend,
        *,
        idle_timeout_minutes: int,
        default_cell_timeout_seconds: int,
        reap_interval_seconds: float = 60.0,
    ) -> None:
        self._backend = backend
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self._default_cell_timeout = default_cell_timeout_seconds
        self._reap_interval_seconds = reap_interval_seconds
        self._handles: dict[str, KernelHandle] = {}
        self._last_used: dict[str, datetime] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._reaper_task: asyncio.Task[None] | None = None

    async def ensure_kernel(
        self, session_id: str, *, on_start: OnStartHook | None = None
    ) -> KernelHandle:
        async with self._locks[session_id]:
            handle = self._handles.get(session_id)
            if handle is not None and await self._backend.is_alive(handle):
                self._touch(session_id)
                return handle

            handle = await self._backend.start_kernel(session_id)
            self._handles[session_id] = handle
            self._touch(session_id)
            if on_start is not None:
                await on_start(handle)
            return handle

    async def run_cell(
        self,
        session_id: str,
        code: str,
        *,
        timeout: float | None = None,
        on_start: OnStartHook | None = None,
    ) -> ExecutionResult:
        handle = await self.ensure_kernel(session_id, on_start=on_start)
        result = await self._backend.execute(
            handle, code, timeout=timeout or self._default_cell_timeout
        )
        self._touch(session_id)
        return result

    async def write_file(
        self,
        session_id: str,
        relative_path: str,
        content: bytes,
        *,
        on_start: OnStartHook | None = None,
    ) -> None:
        handle = await self.ensure_kernel(session_id, on_start=on_start)
        await self._backend.write_file(handle, relative_path, content)
        self._touch(session_id)

    async def shutdown_session(self, session_id: str) -> None:
        handle = self._handles.pop(session_id, None)
        self._last_used.pop(session_id, None)
        if handle is not None:
            await self._backend.shutdown(handle)

    async def shutdown_all(self) -> None:
        for session_id in list(self._handles):
            await self.shutdown_session(session_id)

    def kernel_status(self, session_id: str) -> KernelStatus:
        return "running" if session_id in self._handles else "stopped"

    def _touch(self, session_id: str) -> None:
        self._last_used[session_id] = datetime.now(UTC)

    # -- idle reaper (MASTER_PROMPT.md §3: shut kernels down after an idle timeout) --

    def start_reaper(self) -> None:
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(self._reap_idle_loop())

    async def stop_reaper(self) -> None:
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reaper_task
            self._reaper_task = None

    async def _reap_idle_loop(self) -> None:
        while True:
            await asyncio.sleep(self._reap_interval_seconds)
            cutoff = datetime.now(UTC) - self._idle_timeout
            idle_sessions = [sid for sid, ts in list(self._last_used.items()) if ts < cutoff]
            for session_id in idle_sessions:
                await self.shutdown_session(session_id)


@lru_cache
def get_execution_backend() -> ExecutionBackend:
    return DockerJupyterBackend(get_settings())


@lru_cache
def get_kernel_manager() -> KernelManager:
    settings = get_settings()
    return KernelManager(
        get_execution_backend(),
        idle_timeout_minutes=settings.kernel_idle_timeout_minutes,
        default_cell_timeout_seconds=settings.kernel_cell_timeout_seconds,
    )
