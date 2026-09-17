"""Q&A tests (MASTER_PROMPT.md §5.6, §8, §12 Phase 7).

Most of these go through the API with the real `LLM_MODEL=mock` client (the test-suite
default) — CI must never call a real LLM. Two behaviors mock mode deliberately never exercises
(the LLM deciding it needs new code, and the LLM-unavailable fallback) are tested directly
against `app.agent.qa.answer_question` with a small fake `LLMClient` double instead, the same
way `tests/fakes.py::FakeExecutionBackend` doubles the kernel — see the module docstring in
`app.agent.qa` for why a real, non-mock LLM call is never involved either way.
"""

import io
import zipfile
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import qa
from app.agent.deps import NodeDeps
from app.agent.events import SessionEventBus
from app.agent.llm import LLMBudgetExceededError
from app.agent.tools.schemas import AnswerQuestion
from app.core.config import get_settings
from app.execution.kernel_manager import KernelManager
from app.models.notebook import CellStatus, CellType
from app.models.session import AgentStatus, FileType, SessionStatus, UploadSession
from app.notebook import builder
from app.schemas.dataset import ColumnProfile, DataQualityScore, DatasetProfile
from tests.conftest import FakeStorageBackend
from tests.fakes import FakeExecutionBackend

SAMPLE_DF = pd.DataFrame({"id": range(1, 21), "age": [20 + i for i in range(20)]})


def _upload(client: TestClient) -> str:
    csv_bytes = SAMPLE_DF.to_csv(index=False).encode()
    response = client.post(
        "/sessions", files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert response.status_code == 201
    return response.json()["id"]  # type: ignore[no-any-return]


# --- resolve_cell_references (pure) ----------------------------------------------------------


def test_resolve_cell_references_matches_by_position() -> None:
    cells = [
        type("C", (), {"position": 0})(),
        type("C", (), {"position": 1})(),
        type("C", (), {"position": 2})(),
    ]
    resolved = qa.resolve_cell_references("what does @cell-0 and @cell-2 show?", cells)  # type: ignore[arg-type]
    assert [c.position for c in resolved] == [0, 2]


def test_resolve_cell_references_ignores_unknown_positions() -> None:
    cells = [type("C", (), {"position": 0})()]
    assert qa.resolve_cell_references("what about @cell-99?", cells) == []  # type: ignore[arg-type]


def test_resolve_cell_references_returns_empty_for_no_reference() -> None:
    cells = [type("C", (), {"position": 0})()]
    assert qa.resolve_cell_references("what's in this dataset?", cells) == []  # type: ignore[arg-type]


# --- via the API, real LLM_MODEL=mock client -------------------------------------------------


def test_post_message_answers_and_persists_both_turns(client: TestClient) -> None:
    session_id = _upload(client)
    response = client.post(
        f"/sessions/{session_id}/messages", json={"content": "What columns does this have?"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"]
    assert body["degraded"] is False
    assert body["exploratory_cell_id"] is None

    messages = client.get(f"/sessions/{session_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What columns does this have?"


def test_post_message_references_a_cell_by_position(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/templates/overview/run")
    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    overview_cell = next(c for c in notebook if c["label"] == "Shape & dtypes overview")

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"content": f"What happened in @cell-{overview_cell['position']}?"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["referenced_cell_ids"] == [overview_cell["id"]]
    assert "Shape & dtypes overview" in body["content"]


def test_ask_question_on_unknown_session_404(client: TestClient) -> None:
    response = client.post("/sessions/does-not-exist/messages", json={"content": "hi"})
    assert response.status_code == 404


def test_ask_empty_question_422(client: TestClient) -> None:
    session_id = _upload(client)
    response = client.post(f"/sessions/{session_id}/messages", json={"content": ""})
    assert response.status_code == 422


def test_expertise_level_setting_is_independent_of_auto_decide(client: TestClient) -> None:
    session_id = _upload(client)
    updated = client.post(
        f"/sessions/{session_id}/settings", json={"expertise_level": "expert"}
    ).json()
    assert updated["expertise_level"] == "expert"
    assert updated["auto_decide"] is False

    updated = client.post(f"/sessions/{session_id}/settings", json={"auto_decide": True}).json()
    assert updated["auto_decide"] is True
    assert updated["expertise_level"] == "expert"


# --- direct answer_question() tests with a fake LLM client ------------------------------------


class _FakeLLMClient:
    def __init__(self, result: AnswerQuestion | Exception) -> None:
        self._result = result

    async def complete_structured(
        self, messages: list[dict[str, Any]], response_model: type, **kwargs: Any
    ) -> AnswerQuestion:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


async def _make_ready_session(db: AsyncSession, storage: FakeStorageBackend) -> UploadSession:
    csv_bytes = SAMPLE_DF.to_csv(index=False).encode()
    session = UploadSession(
        original_filename="data.csv",
        storage_key="s1/data.csv",
        file_type=FileType.CSV,
        size_bytes=len(csv_bytes),
        status=SessionStatus.READY,
        profile=DatasetProfile(
            n_rows=20,
            n_columns=2,
            memory_usage_bytes=100,
            is_sampled=False,
            sample_size=None,
            columns=[
                ColumnProfile(
                    name="id", dtype="int64", missing_count=0, missing_pct=0.0, unique_count=20
                ),
                ColumnProfile(
                    name="age", dtype="int64", missing_count=0, missing_pct=0.0, unique_count=20
                ),
            ],
            n_duplicate_rows=0,
            duplicate_pct=0.0,
            constant_columns=[],
            data_quality=DataQualityScore(overall=100.0, breakdown={}, issues=[]),
        ).model_dump(),
    )
    db.add(session)
    await db.flush()
    storage.objects[session.storage_key] = csv_bytes
    await builder.seed_notebook(db, session)
    await db.commit()
    return session


def _deps(
    db: AsyncSession,
    storage: FakeStorageBackend,
    backend: FakeExecutionBackend,
    kernel_manager: KernelManager,
    llm_client: Any,
) -> NodeDeps:
    return NodeDeps(
        db=db,
        storage=storage,
        backend=backend,
        kernel_manager=kernel_manager,
        settings=get_settings(),
        llm_client=llm_client,
        bus=SessionEventBus(),
    )


async def test_answer_question_falls_back_when_llm_unavailable(
    db_session: AsyncSession,
    fake_storage: FakeStorageBackend,
    fake_execution_backend: FakeExecutionBackend,
    kernel_manager: KernelManager,
) -> None:
    session = await _make_ready_session(db_session, fake_storage)
    llm = _FakeLLMClient(LLMBudgetExceededError(session.id, "max calls per session reached"))
    deps = _deps(db_session, fake_storage, fake_execution_backend, kernel_manager, llm)

    message = await qa.answer_question(deps, session, "how many rows are there?")
    assert message.degraded is True
    assert message.content


async def test_answer_question_runs_exploratory_code_when_llm_requests_it(
    db_session: AsyncSession,
    fake_storage: FakeStorageBackend,
    fake_execution_backend: FakeExecutionBackend,
    kernel_manager: KernelManager,
) -> None:
    session = await _make_ready_session(db_session, fake_storage)
    llm = _FakeLLMClient(
        AnswerQuestion(
            answer="Let me check.",
            needs_computation=True,
            code="print(2 + 2)",
            cell_purpose="Check shape",
        )
    )
    deps = _deps(db_session, fake_storage, fake_execution_backend, kernel_manager, llm)

    message = await qa.answer_question(deps, session, "how many rows are there?")
    assert message.exploratory_cell_id is not None

    cells = await builder.get_cells(db_session, session.id)
    exploratory = next(c for c in cells if c.id == message.exploratory_cell_id)
    assert exploratory.is_exploratory is True
    assert exploratory.cell_type == CellType.CODE
    assert exploratory.status == CellStatus.SUCCESS
    assert exploratory.label == "Check shape"


async def test_answer_question_skips_computation_while_agent_is_running(
    db_session: AsyncSession,
    fake_storage: FakeStorageBackend,
    fake_execution_backend: FakeExecutionBackend,
    kernel_manager: KernelManager,
) -> None:
    session = await _make_ready_session(db_session, fake_storage)
    session.agent_status = AgentStatus.RUNNING
    llm = _FakeLLMClient(
        AnswerQuestion(
            answer="Let me check.",
            needs_computation=True,
            code="print(df.shape)",
            cell_purpose=None,
        )
    )
    deps = _deps(db_session, fake_storage, fake_execution_backend, kernel_manager, llm)

    message = await qa.answer_question(deps, session, "how many rows are there?")
    assert message.exploratory_cell_id is None
    assert "actively running" in message.content

    cells = await builder.get_cells(db_session, session.id)
    assert not any(c.is_exploratory for c in cells)


@pytest.mark.parametrize("field", ["referenced_cell_ids", "exploratory_cell_id"])
def test_chat_message_out_schema_has_expected_optional_fields(field: str) -> None:
    from app.schemas.chat import ChatMessageOut

    assert field in ChatMessageOut.model_fields


async def test_export_excludes_exploratory_cells_by_default(
    client: TestClient,
    db_session: AsyncSession,
    fake_storage: FakeStorageBackend,
    fake_execution_backend: FakeExecutionBackend,
    kernel_manager: KernelManager,
) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/templates/overview/run")

    session = await db_session.get(UploadSession, session_id)
    assert session is not None
    llm = _FakeLLMClient(
        AnswerQuestion(
            answer="ok", needs_computation=True, code="print(2 + 2)", cell_purpose="Q&A check"
        )
    )
    deps = _deps(db_session, fake_storage, fake_execution_backend, kernel_manager, llm)
    await qa.answer_question(deps, session, "run something")

    default_export = client.post(f"/sessions/{session_id}/notebook/export")
    assert default_export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(default_export.content)) as zf:
        ipynb_name = next(n for n in zf.namelist() if n.endswith(".ipynb"))
        assert "print(2 + 2)" not in zf.read(ipynb_name).decode()

    full_export = client.post(f"/sessions/{session_id}/notebook/export?include_exploratory=true")
    assert full_export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(full_export.content)) as zf:
        ipynb_name = next(n for n in zf.namelist() if n.endswith(".ipynb"))
        assert "print(2 + 2)" in zf.read(ipynb_name).decode()
