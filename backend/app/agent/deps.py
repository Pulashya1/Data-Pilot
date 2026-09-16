"""Per-run dependency registry for agent nodes (MASTER_PROMPT.md §12 Phase 3).

LangGraph checkpoints `AgentState` (see `app/agent/state.py`), which must stay small and
JSON-serializable — it can't hold a DB session, the kernel manager, or the LLM client. Nodes
instead look those up here by `session_id`; `AgentRunner` (`app/agent/runner.py`) registers
them right before invoking the graph and unregisters them when the run ends.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.events import SessionEventBus
from app.agent.llm import LLMClient
from app.core.config import Settings
from app.core.storage import StorageBackend
from app.execution.backend import ExecutionBackend
from app.execution.kernel_manager import KernelManager


@dataclass
class NodeDeps:
    db: AsyncSession
    storage: StorageBackend
    backend: ExecutionBackend
    kernel_manager: KernelManager
    settings: Settings
    llm_client: LLMClient
    bus: SessionEventBus


_registry: dict[str, NodeDeps] = {}


def register(session_id: str, deps: NodeDeps) -> None:
    _registry[session_id] = deps


def get(session_id: str) -> NodeDeps:
    return _registry[session_id]


def unregister(session_id: str) -> None:
    _registry.pop(session_id, None)
