"""In-memory `ExecutionBackend` double for tests: runs cell code with a real Python `exec`
(in a per-session namespace, with pandas/numpy/matplotlib available) instead of Docker, so
API and KernelManager tests exercise the real generated code without needing a container.
"""

import contextlib
import io
import os
import tempfile
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set before this import)

from app.execution.backend import KernelHandle, KernelStartupError
from app.schemas.execution import ExecutionResult


class FakeExecutionBackend:
    def __init__(self) -> None:
        self.namespaces: dict[str, dict[str, Any]] = {}
        self.workdirs: dict[str, Path] = {}
        self.alive: dict[str, bool] = {}
        self.start_count = 0
        self.fail_next_start = False

    async def start_kernel(self, session_id: str) -> KernelHandle:
        self.start_count += 1
        if self.fail_next_start:
            self.fail_next_start = False
            raise KernelStartupError("simulated startup failure")
        self.namespaces[session_id] = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "sns": sns,
            "json": __import__("json"),
            "display": lambda *a, **k: None,
        }
        self.workdirs[session_id] = Path(tempfile.mkdtemp(prefix=f"fake-kernel-{session_id}-"))
        self.alive[session_id] = True
        return KernelHandle(session_id=session_id, kernel_id=f"fake-{session_id}", state={})

    async def execute(self, handle: KernelHandle, code: str, *, timeout: float) -> ExecutionResult:
        session_id = handle.session_id
        namespace = self.namespaces.setdefault(session_id, {})
        workdir = self.workdirs.setdefault(session_id, Path(tempfile.mkdtemp()))
        stdout = io.StringIO()
        status = "ok"
        error_message = None
        outputs: list[dict[str, Any]] = []

        # A real kernel runs cells through IPython's input transformer, which understands
        # magics like `%matplotlib inline`; plain exec() doesn't, so strip them here.
        plain_code = "\n".join(
            line for line in code.splitlines() if not line.lstrip().startswith("%")
        )

        original_cwd = Path.cwd()
        os.chdir(workdir)
        try:
            with contextlib.redirect_stdout(stdout):
                exec(compile(plain_code, "<cell>", "exec"), namespace)  # noqa: S102
        except Exception as exc:  # noqa: BLE001 - mirrors a real kernel's error output
            status = "error"
            error_message = f"{type(exc).__name__}: {exc}"
        finally:
            os.chdir(original_cwd)

        text = stdout.getvalue()
        if text:
            outputs.append({"output_type": "stream", "name": "stdout", "text": text})
        if status == "error":
            outputs.append(
                {
                    "output_type": "error",
                    "ename": error_message.split(":", 1)[0] if error_message else "Error",
                    "evalue": error_message or "",
                    "traceback": [error_message or ""],
                }
            )
        return ExecutionResult(
            status=status, outputs=outputs, execution_count=1, error_message=error_message
        )

    async def write_file(self, handle: KernelHandle, relative_path: str, content: bytes) -> None:
        workdir = self.workdirs.setdefault(
            handle.session_id, Path(tempfile.mkdtemp(prefix=f"fake-kernel-{handle.session_id}-"))
        )
        target = workdir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    async def interrupt(self, handle: KernelHandle) -> None:
        return None

    async def is_alive(self, handle: KernelHandle) -> bool:
        return self.alive.get(handle.session_id, False)

    async def shutdown(self, handle: KernelHandle) -> None:
        self.alive[handle.session_id] = False
        self.namespaces.pop(handle.session_id, None)
        self.workdirs.pop(handle.session_id, None)

    def kill_session(self, session_id: str) -> None:
        """Test helper: simulate a crashed kernel without going through shutdown()."""
        self.alive[session_id] = False


class FakeRedis:
    """In-memory stand-in for `app.core.redis.RedisLike`, used by LLM client tests so they
    don't need a real Redis server. TTLs are tracked but not actively expired — tests that
    care about expiry check `expire_seconds` directly instead of sleeping."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expire_seconds: dict[str, int] = {}

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> None:
        self.values[name] = value
        if ex is not None:
            self.expire_seconds[name] = ex

    async def incrby(self, name: str, amount: int = 1) -> int:
        current = int(self.values.get(name) or 0) + amount
        self.values[name] = str(current)
        return current

    async def expire(self, name: str, seconds: int) -> None:
        self.expire_seconds[name] = seconds
