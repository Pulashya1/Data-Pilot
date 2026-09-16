"""Docker-sandboxed `ExecutionBackend` (MASTER_PROMPT.md §3, §9, §12 Phase 2).

Every kernel runs as two containers, built from `backend/kernel_image/` and
`backend/relay_image/`:

- **kernel**: attached only to an internal (no-internet) Docker network, read-only root
  filesystem, non-root user, CPU/memory limits. It cannot reach anything outside that
  network — verified experimentally: a container on an `internal=True` Docker network has
  no outbound route at all, not even to the host.
- **relay**: a small, fixed `socat` process (never runs user code) that sits on both the
  internal network and a public one, forwarding the 5 Jupyter ZMQ ports. It's the only way
  the host can reach the kernel; published ports are bound to `127.0.0.1` only. Docker only
  publishes ports on a container's network *if that network was attached at creation time
  and isn't internal* — so the relay is created on the public network first, and the
  internal network is attached afterward via `network.connect()`.

The backend talks to the kernel over ZMQ via `jupyter_client`'s `BlockingKernelClient`,
run inside `asyncio.to_thread` since it's a blocking API.
"""

import asyncio
import contextlib
import json
import secrets
import shutil
import socket
import tempfile
import time
from pathlib import Path
from queue import Empty
from typing import Any
from uuid import uuid4

import docker
from docker.models.containers import Container
from jupyter_client import BlockingKernelClient

from app.core.config import Settings
from app.execution.backend import KernelHandle, KernelStartupError
from app.schemas.execution import ExecutionResult, ExecutionStatus

_CONNECTION_PORT_NAMES = ("shell_port", "iopub_port", "stdin_port", "control_port", "hb_port")


def _free_ports(n: int) -> list[int]:
    socks = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(n)]
    try:
        for s in socks:
            s.bind(("127.0.0.1", 0))
        return [s.getsockname()[1] for s in socks]
    finally:
        for s in socks:
            s.close()


class DockerJupyterBackend:
    """Real `ExecutionBackend` implementation using the Docker SDK + jupyter_client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: docker.DockerClient | None = None

    def _docker(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _ensure_networks(self) -> None:
        client = self._docker()
        for name, kwargs in (
            (self._settings.kernel_network_internal, {"internal": True}),
            (self._settings.kernel_network_public, {}),
        ):
            try:
                client.networks.get(name)
            except docker.errors.NotFound:
                with contextlib.suppress(docker.errors.APIError):
                    client.networks.create(name, driver="bridge", **kwargs)

    # -- ExecutionBackend -----------------------------------------------------------

    async def start_kernel(self, session_id: str) -> KernelHandle:
        return await asyncio.to_thread(self._start_kernel_sync, session_id)

    async def execute(self, handle: KernelHandle, code: str, *, timeout: float) -> ExecutionResult:
        status, outputs, execution_count, error_message, aborted = await asyncio.to_thread(
            self._execute_sync, handle, code, timeout
        )
        if aborted:
            # The kernel replied "abort" instead of running the cell — this happens when a
            # cell is submitted while the kernel is still draining the queue left behind by
            # interrupting a *previous* timed-out cell. It's a transient race, not a real
            # failure, so retry once now that the abort queue has had time to clear.
            status, outputs, execution_count, error_message, _ = await asyncio.to_thread(
                self._execute_sync, handle, code, timeout
            )
        if status == "timeout":
            await self.interrupt(handle)
        return ExecutionResult(
            status=status,
            outputs=outputs,
            execution_count=execution_count,
            error_message=error_message,
        )

    async def write_file(self, handle: KernelHandle, relative_path: str, content: bytes) -> None:
        await asyncio.to_thread(self._write_file_sync, handle, relative_path, content)

    async def interrupt(self, handle: KernelHandle) -> None:
        await asyncio.to_thread(self._interrupt_sync, handle)

    async def is_alive(self, handle: KernelHandle) -> bool:
        return await asyncio.to_thread(self._is_alive_sync, handle)

    async def shutdown(self, handle: KernelHandle) -> None:
        await asyncio.to_thread(self._shutdown_sync, handle)

    # -- sync implementations (run inside asyncio.to_thread) ------------------------

    def _start_kernel_sync(self, session_id: str) -> KernelHandle:
        self._ensure_networks()
        docker_client = self._docker()

        ports = _free_ports(5)
        key = secrets.token_hex(32)

        workdir = Path(tempfile.mkdtemp(prefix=f"datapilot-kernel-{session_id}-"))
        work_mount = workdir / "work"
        work_mount.mkdir()

        base_conn: dict[str, Any] = dict(zip(_CONNECTION_PORT_NAMES, ports, strict=True))
        base_conn.update(
            {
                "transport": "tcp",
                "key": key,
                "signature_scheme": "hmac-sha256",
                "kernel_name": "python3",
            }
        )
        container_conn_path = workdir / "container_connection.json"
        host_conn_path = workdir / "host_connection.json"
        container_conn_path.write_text(json.dumps({**base_conn, "ip": "0.0.0.0"}))
        host_conn_path.write_text(json.dumps({**base_conn, "ip": "127.0.0.1"}))

        # Container names double as the DNS name the relay resolves to reach the kernel
        # (`RELAY_TARGET` below), so they must fit in a single 63-character DNS label —
        # a short random suffix is used instead of embedding the (unbounded-length)
        # session_id, which is kept in a label for lookup/debugging instead.
        suffix = uuid4().hex
        kernel_name = f"dp-kernel-{suffix}"
        relay_name = f"dp-relay-{suffix}"
        labels = {"datapilot.session_id": session_id}

        kernel_container = docker_client.containers.run(
            self._settings.kernel_image,
            detach=True,
            name=kernel_name,
            network=self._settings.kernel_network_internal,
            read_only=True,
            tmpfs={"/tmp": "size=512m"},
            user="1000:1000",
            mem_limit=self._settings.kernel_memory_limit,
            nano_cpus=int(self._settings.kernel_cpu_limit * 1_000_000_000),
            volumes={
                str(container_conn_path): {"bind": "/home/kernel/connection.json", "mode": "rw"},
                str(work_mount): {"bind": "/home/kernel/work", "mode": "rw"},
            },
            labels={**labels, "datapilot.role": "kernel"},
        )

        try:
            relay_container = docker_client.containers.run(
                self._settings.kernel_relay_image,
                detach=True,
                name=relay_name,
                network=self._settings.kernel_network_public,
                ports={f"{p}/tcp": ("127.0.0.1", p) for p in ports},
                environment={
                    "RELAY_TARGET": kernel_name,
                    "RELAY_PORTS": " ".join(str(p) for p in ports),
                },
                labels={**labels, "datapilot.role": "relay"},
            )
            docker_client.networks.get(self._settings.kernel_network_internal).connect(
                relay_container
            )
        except Exception:
            self._force_remove(kernel_container)
            shutil.rmtree(workdir, ignore_errors=True)
            raise

        client = BlockingKernelClient()
        client.load_connection_file(str(host_conn_path))
        client.start_channels()
        try:
            client.wait_for_ready(timeout=self._settings.kernel_startup_timeout_seconds)
        except Exception as exc:
            with contextlib.suppress(Exception):
                client.stop_channels()
            self._force_remove(kernel_container)
            self._force_remove(relay_container)
            shutil.rmtree(workdir, ignore_errors=True)
            raise KernelStartupError(
                f"Kernel for session {session_id} did not become ready"
            ) from exc

        return KernelHandle(
            session_id=session_id,
            kernel_id=kernel_container.id,
            state={
                "kernel_container_id": kernel_container.id,
                "relay_container_id": relay_container.id,
                "client": client,
                "workdir": str(workdir),
                "work_mount": str(work_mount),
            },
        )

    def _execute_sync(
        self, handle: KernelHandle, code: str, timeout: float
    ) -> tuple[ExecutionStatus, list[dict[str, Any]], int | None, str | None, bool]:
        client: BlockingKernelClient = handle.state["client"]
        msg_id = client.execute(code)
        outputs: list[dict[str, Any]] = []
        error_message: str | None = None
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "timeout", outputs, None, "Cell execution timed out.", False
            try:
                msg = client.get_iopub_msg(timeout=min(remaining, 1.0))
            except Empty:
                continue
            if msg["parent_header"].get("msg_id") != msg_id:
                continue
            msg_type = msg["msg_type"]
            content = msg["content"]
            if msg_type == "stream":
                outputs.append(
                    {"output_type": "stream", "name": content["name"], "text": content["text"]}
                )
            elif msg_type == "execute_result":
                outputs.append(
                    {
                        "output_type": "execute_result",
                        "data": content["data"],
                        "metadata": content.get("metadata", {}),
                        "execution_count": content.get("execution_count"),
                    }
                )
            elif msg_type == "display_data":
                outputs.append(
                    {
                        "output_type": "display_data",
                        "data": content["data"],
                        "metadata": content.get("metadata", {}),
                    }
                )
            elif msg_type == "error":
                error_message = "\n".join(
                    content.get("traceback") or [f"{content.get('ename')}: {content.get('evalue')}"]
                )
                outputs.append(
                    {
                        "output_type": "error",
                        "ename": content.get("ename"),
                        "evalue": content.get("evalue"),
                        "traceback": content.get("traceback", []),
                    }
                )
            elif msg_type == "status" and content.get("execution_state") == "idle":
                break

        status: ExecutionStatus = "error" if error_message else "ok"
        execution_count = None
        aborted = False
        with contextlib.suppress(Empty):
            remaining = max(0.1, deadline - time.monotonic())
            while True:
                reply = client.get_shell_msg(timeout=remaining)
                if reply["parent_header"].get("msg_id") == msg_id:
                    execution_count = reply["content"].get("execution_count")
                    reply_status = reply["content"].get("status")
                    if reply_status == "ok":
                        status = "ok"
                    elif reply_status == "error":
                        status = "error"
                    elif reply_status is not None:
                        # A status the kernel can report that isn't in our own 3-value
                        # model — most commonly "abort" (queued during another cell's
                        # interrupt). Treat as an error unless the caller retries.
                        aborted = True
                        status = "error"
                        error_message = error_message or f"Kernel reported status: {reply_status!r}"
                    break
        return status, outputs, execution_count, error_message, aborted

    def _write_file_sync(self, handle: KernelHandle, relative_path: str, content: bytes) -> None:
        work_mount = Path(handle.state["work_mount"])
        target = (work_mount / relative_path).resolve()
        if work_mount.resolve() not in target.parents:
            raise ValueError(f"Refusing to write outside kernel work directory: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def _interrupt_sync(self, handle: KernelHandle) -> None:
        with contextlib.suppress(docker.errors.NotFound, docker.errors.APIError):
            self._docker().containers.get(handle.state["kernel_container_id"]).kill(signal="SIGINT")

    def _is_alive_sync(self, handle: KernelHandle) -> bool:
        try:
            container = self._docker().containers.get(handle.state["kernel_container_id"])
        except docker.errors.NotFound:
            return False
        return bool(container.status == "running")

    def _shutdown_sync(self, handle: KernelHandle) -> None:
        client: BlockingKernelClient | None = handle.state.get("client")
        if client is not None:
            with contextlib.suppress(Exception):
                client.stop_channels()
        for key in ("kernel_container_id", "relay_container_id"):
            container_id = handle.state.get(key)
            if container_id:
                self._force_remove_by_id(container_id)
        workdir = handle.state.get("workdir")
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    def _force_remove(self, container: Container) -> None:
        with contextlib.suppress(docker.errors.NotFound, docker.errors.APIError):
            container.remove(force=True)

    def _force_remove_by_id(self, container_id: str) -> None:
        with contextlib.suppress(docker.errors.NotFound, docker.errors.APIError):
            self._docker().containers.get(container_id).remove(force=True)
