"""Unit tests for app.notebook.builder (pure DB logic, no kernel)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import CellStatus, CellType
from app.models.session import FileType, SessionStatus, UploadSession
from app.notebook import builder
from app.schemas.execution import ExecutionResult


async def _make_session(db: AsyncSession, **overrides: object) -> UploadSession:
    defaults: dict[str, object] = {
        "original_filename": "sales.csv",
        "storage_key": "sess/sales.csv",
        "file_type": FileType.CSV,
        "size_bytes": 100,
        "status": SessionStatus.READY,
    }
    defaults.update(overrides)
    session = UploadSession(**defaults)
    db.add(session)
    await db.flush()
    return session


async def test_seed_notebook_creates_standard_opening_cells(db_session: AsyncSession) -> None:
    session = await _make_session(db_session)
    cells = await builder.seed_notebook(db_session, session)

    assert [c.cell_type for c in cells] == [
        CellType.MARKDOWN,
        CellType.CODE,
        CellType.CODE,
        CellType.CODE,
    ]
    assert cells[1].label == "Imports"
    assert cells[2].label == "Configuration"
    assert cells[3].label == "Load data"
    assert 'pd.read_csv("data/sales.csv")' in cells[3].source
    assert [c.position for c in cells] == [0, 1, 2, 3]


async def test_seed_notebook_is_idempotent(db_session: AsyncSession) -> None:
    session = await _make_session(db_session)
    first = await builder.seed_notebook(db_session, session)
    second = await builder.seed_notebook(db_session, session)
    assert [c.id for c in first] == [c.id for c in second]


async def test_seed_notebook_excel_uses_sheet_name(db_session: AsyncSession) -> None:
    session = await _make_session(
        db_session,
        original_filename="book.xlsx",
        file_type=FileType.EXCEL,
        selected_sheet="Sheet2",
    )
    cells = await builder.seed_notebook(db_session, session)
    assert "sheet_name='Sheet2'" in cells[3].source


async def test_add_code_cell_increments_position(db_session: AsyncSession) -> None:
    session = await _make_session(db_session)
    first = await builder.add_code_cell(db_session, session.id, "1 + 1", label="A")
    second = await builder.add_code_cell(db_session, session.id, "2 + 2", label="B")
    assert first.position == 0
    assert second.position == 1


async def test_apply_execution_result_success(db_session: AsyncSession) -> None:
    session = await _make_session(db_session)
    cell = await builder.add_code_cell(db_session, session.id, "1 + 1", label="A")
    result = ExecutionResult(
        status="ok",
        outputs=[{"output_type": "stream", "name": "stdout", "text": "2\n"}],
        execution_count=1,
    )
    builder.apply_execution_result(cell, result)
    assert cell.status == CellStatus.SUCCESS
    assert cell.execution_count == 1
    assert cell.outputs == result.outputs


async def test_apply_execution_result_error(db_session: AsyncSession) -> None:
    session = await _make_session(db_session)
    cell = await builder.add_code_cell(db_session, session.id, "1 / 0", label="A")
    result = ExecutionResult(status="error", outputs=[], error_message="ZeroDivisionError")
    builder.apply_execution_result(cell, result)
    assert cell.status == CellStatus.ERROR
    assert cell.error_message == "ZeroDivisionError"
