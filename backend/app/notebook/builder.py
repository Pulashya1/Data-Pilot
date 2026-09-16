"""Builds and persists the live notebook for a session (MASTER_PROMPT.md §6, §12 Phase 2).

Cells are rows in `notebook_cells`, ordered by `position`; nothing here talks to the kernel
directly (see `app.execution.kernel_manager`) or exports to `.ipynb` (see `app.notebook.export`).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import CellStatus, CellType, NotebookCell
from app.models.session import FileType, UploadSession
from app.schemas.execution import ExecutionResult

_LOAD_CODE: dict[FileType, str] = {
    FileType.CSV: 'df_raw = pd.read_csv("data/{filename}")',
    FileType.TSV: 'df_raw = pd.read_csv("data/{filename}", sep="\\t")',
    FileType.EXCEL: 'df_raw = pd.read_excel("data/{filename}", sheet_name={sheet!r})',
    FileType.JSON: 'df_raw = pd.read_json("data/{filename}")',
    FileType.JSON_LINES: 'df_raw = pd.read_json("data/{filename}", lines=True)',
    FileType.PARQUET: 'df_raw = pd.read_parquet("data/{filename}")',
}


async def get_cells(db: AsyncSession, session_id: str) -> list[NotebookCell]:
    result = await db.execute(
        select(NotebookCell)
        .where(NotebookCell.session_id == session_id)
        .order_by(NotebookCell.position)
    )
    return list(result.scalars().all())


async def _next_position(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(func.max(NotebookCell.position)).where(NotebookCell.session_id == session_id)
    )
    current_max = result.scalar_one_or_none()
    return 0 if current_max is None else current_max + 1


async def add_markdown_cell(db: AsyncSession, session_id: str, source: str) -> NotebookCell:
    cell = NotebookCell(
        session_id=session_id,
        position=await _next_position(db, session_id),
        cell_type=CellType.MARKDOWN,
        source=source,
        status=CellStatus.SUCCESS,
    )
    db.add(cell)
    await db.flush()
    return cell


async def add_code_cell(
    db: AsyncSession, session_id: str, source: str, *, label: str
) -> NotebookCell:
    cell = NotebookCell(
        session_id=session_id,
        position=await _next_position(db, session_id),
        cell_type=CellType.CODE,
        source=source,
        label=label,
        status=CellStatus.PENDING,
    )
    db.add(cell)
    await db.flush()
    return cell


def apply_execution_result(cell: NotebookCell, result: ExecutionResult) -> None:
    cell.outputs = result.outputs
    cell.execution_count = result.execution_count
    cell.status = CellStatus.SUCCESS if result.status == "ok" else CellStatus.ERROR
    cell.error_message = result.error_message


async def seed_notebook(db: AsyncSession, session: UploadSession) -> list[NotebookCell]:
    """Create the standard opening cells (title, imports, seed, data load) if not present."""
    existing = await get_cells(db, session.id)
    if existing:
        return existing

    await add_markdown_cell(
        db,
        session.id,
        f"# DataPilot analysis: {session.original_filename}\n\n"
        f"Generated {session.created_at:%Y-%m-%d %H:%M} UTC. Problem type: not yet determined.\n\n"
        "## Table of contents\n1. Setup\n2. Data loading",
    )
    imports_code = (
        "import json\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "import seaborn as sns\n"
        "from IPython.display import display\n\n"
        '%matplotlib inline\nsns.set_theme(style="whitegrid")'
    )
    await add_code_cell(db, session.id, imports_code, label="Imports")
    await add_code_cell(db, session.id, "SEED = 42\nnp.random.seed(SEED)", label="Configuration")

    load_template = _LOAD_CODE[session.file_type]
    load_code = load_template.format(
        filename=session.original_filename, sheet=session.selected_sheet
    )
    load_code += "\ndf = df_raw.copy()\ndf.shape"
    await add_code_cell(db, session.id, load_code, label="Load data")

    return await get_cells(db, session.id)
