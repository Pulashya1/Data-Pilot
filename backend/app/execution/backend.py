"""Backend-agnostic sandboxed code execution interface (MASTER_PROMPT.md §2, §3, §9).

`ExecutionBackend` is deliberately narrow so a non-Docker backend (e.g. E2B) can be
swapped in later without touching `KernelManager` or anything above it.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.schemas.execution import ExecutionResult


class KernelStartupError(RuntimeError):
    """Raised when a kernel fails to start or become ready in time."""


@dataclass
class KernelHandle:
    """An opaque handle to a running kernel. `state` is backend-private."""

    session_id: str
    kernel_id: str
    state: dict[str, Any] = field(default_factory=dict)


class ExecutionBackend(Protocol):
    async def start_kernel(self, session_id: str) -> KernelHandle: ...

    async def execute(
        self, handle: KernelHandle, code: str, *, timeout: float
    ) -> ExecutionResult: ...

    async def write_file(self, handle: KernelHandle, relative_path: str, content: bytes) -> None:
        """Seed a file (e.g. the dataset) into the kernel's working directory."""
        ...

    async def interrupt(self, handle: KernelHandle) -> None: ...

    async def is_alive(self, handle: KernelHandle) -> bool: ...

    async def shutdown(self, handle: KernelHandle) -> None: ...
