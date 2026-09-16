"""Integration tests against the real `DockerJupyterBackend` (MASTER_PROMPT.md §10).

Not part of the default `pytest` run (see CLAUDE.md) — build the images first:

    docker build -t datapilot-kernel:latest kernel_image/
    docker build -t datapilot-kernel-relay:latest relay_image/

then run:

    pytest -m docker

Skips automatically if Docker isn't reachable or the images aren't built, so it's safe to
leave in the default collection.
"""

import contextlib
from collections.abc import AsyncGenerator

import docker
import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.execution.backend import KernelHandle
from app.execution.docker_backend import DockerJupyterBackend


def _docker_ready() -> bool:
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    settings = get_settings()
    try:
        client.images.get(settings.kernel_image)
        client.images.get(settings.kernel_relay_image)
    except docker.errors.ImageNotFound:
        return False
    return True


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        not _docker_ready(),
        reason="Docker isn't reachable, or datapilot-kernel(-relay) images aren't built",
    ),
]


@pytest.fixture
def backend() -> DockerJupyterBackend:
    return DockerJupyterBackend(get_settings())


@pytest_asyncio.fixture
async def handle(backend: DockerJupyterBackend) -> AsyncGenerator[KernelHandle]:
    started = await backend.start_kernel("it-" + str(id(backend)))
    try:
        yield started
    finally:
        with contextlib.suppress(Exception):
            await backend.shutdown(started)


async def test_execute_runs_code_and_returns_stdout(
    backend: DockerJupyterBackend, handle: KernelHandle
) -> None:
    result = await backend.execute(handle, "print(1 + 1)", timeout=30)
    assert result.status == "ok"
    assert result.outputs[0]["text"].strip() == "2"


async def test_execute_reports_errors(backend: DockerJupyterBackend, handle: KernelHandle) -> None:
    result = await backend.execute(handle, "1 / 0", timeout=30)
    assert result.status == "error"
    assert "ZeroDivisionError" in (result.error_message or "")


async def test_kernel_has_no_outbound_network(
    backend: DockerJupyterBackend, handle: KernelHandle
) -> None:
    result = await backend.execute(
        handle,
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://142.250.72.14', timeout=4)\n"
        "    print('REACHED')\n"
        "except Exception as e:\n"
        "    print('BLOCKED', type(e).__name__)\n",
        timeout=30,
    )
    assert result.status == "ok"
    assert "BLOCKED" in result.outputs[0]["text"]


async def test_write_file_is_visible_to_a_data_loading_cell(
    backend: DockerJupyterBackend, handle: KernelHandle
) -> None:
    await backend.write_file(handle, "data/sample.csv", b"a,b\n1,2\n3,4\n")
    result = await backend.execute(
        handle,
        'import pandas as pd\ndf = pd.read_csv("data/sample.csv")\nprint(len(df))',
        timeout=30,
    )
    assert result.status == "ok"
    assert result.outputs[0]["text"].strip() == "2"


async def test_cell_timeout_interrupts_the_kernel(
    backend: DockerJupyterBackend, handle: KernelHandle
) -> None:
    result = await backend.execute(handle, "import time\ntime.sleep(30)", timeout=2)
    assert result.status == "timeout"
    # the kernel should recover and accept new code afterward
    follow_up = await backend.execute(handle, "print('still alive')", timeout=30)
    assert follow_up.status == "ok"


async def test_is_alive_and_crash_recovery(
    backend: DockerJupyterBackend, handle: KernelHandle
) -> None:
    assert await backend.is_alive(handle) is True
    client = docker.from_env()
    client.containers.get(handle.state["kernel_container_id"]).kill()
    assert await backend.is_alive(handle) is False
