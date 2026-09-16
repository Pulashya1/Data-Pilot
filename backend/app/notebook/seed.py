"""Kernel warm-up and template-step execution shared by the manual template API
(`app/api/notebook.py`, Phase 2) and the agent's `execute_step` node (`app/agent/nodes.py`,
Phase 3) — extracted so neither re-implements the render -> run -> summarize -> insight-cell
sequence.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.templates.base import Template, extract_summary
from app.core.config import Settings
from app.core.storage import StorageBackend
from app.execution.backend import ExecutionBackend, KernelHandle
from app.execution.kernel_manager import KernelManager, OnStartHook
from app.models.notebook import CellStatus, CellType, NotebookCell
from app.models.session import UploadSession
from app.notebook import builder
from app.schemas.dataset import DatasetProfile


def make_on_start_hook(
    session: UploadSession,
    db: AsyncSession,
    storage: StorageBackend,
    backend: ExecutionBackend,
    settings: Settings,
) -> OnStartHook:
    """Seeds the dataset file and replays previously-successful cells into a freshly (re)started
    kernel — MASTER_PROMPT.md §3: "kernel rebuilt by re-executing the notebook's accepted cells"."""

    async def on_start(handle: KernelHandle) -> None:
        raw = storage.download(session.storage_key)
        await backend.write_file(handle, f"data/{session.original_filename}", raw)
        cells = await builder.get_cells(db, session.id)
        for cell in cells:
            if cell.cell_type == CellType.CODE and cell.status == CellStatus.SUCCESS:
                await backend.execute(
                    handle, cell.source, timeout=settings.kernel_cell_timeout_seconds
                )

    return on_start


async def run_pending_seed_cells(
    session: UploadSession,
    db: AsyncSession,
    storage: StorageBackend,
    backend: ExecutionBackend,
    kernel_manager: KernelManager,
    settings: Settings,
) -> None:
    """Run any not-yet-executed seed cells (imports/config/data load) before new work."""
    on_start: OnStartHook | None = make_on_start_hook(session, db, storage, backend, settings)
    cells = await builder.get_cells(db, session.id)
    for cell in cells:
        if cell.cell_type != CellType.CODE or cell.status != CellStatus.PENDING:
            continue
        result = await kernel_manager.run_cell(session.id, cell.source, on_start=on_start)
        on_start = None  # only needed once, to seed a brand-new kernel
        extract_summary(result)
        builder.apply_execution_result(cell, result)
        await db.flush()


async def render_and_run_template_step(
    db: AsyncSession,
    session: UploadSession,
    storage: StorageBackend,
    backend: ExecutionBackend,
    kernel_manager: KernelManager,
    settings: Settings,
    template: Template,
) -> tuple[list[NotebookCell], dict[str, Any] | None]:
    """Render `template`, run it in the session's kernel, and append its insight bullets as a
    markdown cell. Returns every cell created (the code cell, plus an insight cell if any) and
    the raw `##DATAPILOT_SUMMARY##` dict (so callers like the agent's `execute_step` node can
    classify insight severity without re-parsing cell output).

    `target_column`/`problem_type` are injected here rather than threaded through
    `Template.default_params`'s signature, so every existing template (which only takes
    `profile`) is unaffected; problem-type-specific templates (MASTER_PROMPT.md §5.3, §12
    Phase 5) read them out of `params` and degrade to a no-target summary when absent (e.g. the
    manual `POST /templates/{key}/run` API, or a session with no confirmed target).
    """
    profile = DatasetProfile.model_validate(session.profile)
    params = {
        **template.default_params(profile),
        "target_column": session.target_column,
        "problem_type": session.problem_type.value if session.problem_type else None,
    }
    code = template.render(params)
    cell = await builder.add_code_cell(db, session.id, code, label=template.title)
    await db.flush()

    on_start = make_on_start_hook(session, db, storage, backend, settings)
    result = await kernel_manager.run_cell(session.id, code, on_start=on_start)

    summary = extract_summary(result)
    builder.apply_execution_result(cell, result)
    await db.flush()

    new_cells: list[NotebookCell] = [cell]
    if summary is not None:
        insights = template.summarize(summary)
        if insights:
            markdown = "**Insights:**\n\n" + "\n".join(f"- {line}" for line in insights)
            insight_cell = await builder.add_markdown_cell(db, session.id, markdown)
            await db.flush()
            new_cells.append(insight_cell)
    return new_cells, summary
