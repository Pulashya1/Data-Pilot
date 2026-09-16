"""Unit tests for KernelManager orchestration, using FakeExecutionBackend (no Docker)."""

import asyncio

import pytest

from app.execution.kernel_manager import KernelManager
from tests.fakes import FakeExecutionBackend


@pytest.fixture
def backend() -> FakeExecutionBackend:
    return FakeExecutionBackend()


@pytest.fixture
def manager(backend: FakeExecutionBackend) -> KernelManager:
    return KernelManager(backend, idle_timeout_minutes=30, default_cell_timeout_seconds=30)


async def test_run_cell_starts_a_kernel_on_first_use(
    manager: KernelManager, backend: FakeExecutionBackend
) -> None:
    result = await manager.run_cell("s1", "print(1 + 1)")
    assert result.status == "ok"
    assert backend.start_count == 1
    assert manager.kernel_status("s1") == "running"


async def test_run_cell_reuses_the_same_kernel(
    manager: KernelManager, backend: FakeExecutionBackend
) -> None:
    await manager.run_cell("s1", "x = 1")
    await manager.run_cell("s1", "x += 1")
    result = await manager.run_cell("s1", "print(x)")
    assert backend.start_count == 1
    assert result.outputs[0]["text"].strip() == "2"


async def test_on_start_hook_only_fires_on_a_fresh_kernel(
    manager: KernelManager, backend: FakeExecutionBackend
) -> None:
    calls = []

    async def on_start(handle: object) -> None:
        calls.append(handle)

    await manager.run_cell("s1", "x = 1", on_start=on_start)
    await manager.run_cell("s1", "x = 2", on_start=on_start)
    assert len(calls) == 1


async def test_crash_recovery_starts_a_new_kernel_and_fires_on_start(
    manager: KernelManager, backend: FakeExecutionBackend
) -> None:
    await manager.run_cell("s1", "x = 1")
    backend.kill_session("s1")

    calls = []

    async def on_start(handle: object) -> None:
        calls.append(handle)

    result = await manager.run_cell("s1", "print('recovered')", on_start=on_start)
    assert result.status == "ok"
    assert backend.start_count == 2
    assert len(calls) == 1


async def test_shutdown_session_removes_tracking(
    manager: KernelManager, backend: FakeExecutionBackend
) -> None:
    await manager.run_cell("s1", "x = 1")
    await manager.shutdown_session("s1")
    assert manager.kernel_status("s1") == "stopped"
    assert backend.alive.get("s1") is False


async def test_idle_reaper_shuts_down_kernels_past_the_timeout() -> None:
    backend = FakeExecutionBackend()
    manager = KernelManager(
        backend,
        idle_timeout_minutes=0,
        default_cell_timeout_seconds=30,
        reap_interval_seconds=0.05,
    )
    await manager.run_cell("s1", "x = 1")
    manager.start_reaper()
    try:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if manager.kernel_status("s1") == "stopped":
                break
        assert manager.kernel_status("s1") == "stopped"
    finally:
        await manager.stop_reaper()
