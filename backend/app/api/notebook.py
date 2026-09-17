"""Notebook, template, and kernel endpoints (MASTER_PROMPT.md §8, §12 Phase 2/4).

No LLM involved: templates are rendered deterministically (app/analysis/templates) and run
in the session's sandboxed kernel (app/execution). The agent (Phase 3+) drives these same
building blocks instead of explicit UI buttons.
"""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.templates.registry import TEMPLATES
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.storage import StorageBackend, get_storage_backend
from app.execution.backend import ExecutionBackend, KernelStartupError
from app.execution.kernel_manager import (
    KernelManager,
    get_execution_backend,
    get_kernel_manager,
)
from app.models.notebook import CellType, NotebookCell
from app.models.session import AgentStatus, SessionStatus, UploadSession
from app.notebook import builder
from app.notebook.export import build_export_zip, read_kernel_requirements
from app.notebook.seed import render_and_run_template_step, run_pending_seed_cells
from app.schemas.notebook import KernelStatusOut, NotebookCellOut, TemplateInfo

router = APIRouter(tags=["notebook"])


async def _get_ready_session_or_404(session_id: str, db: AsyncSession) -> UploadSession:
    session = await db.get(UploadSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.READY or session.profile is None:
        raise HTTPException(status_code=409, detail="Session is not ready for analysis")
    return session


@router.get("/templates", response_model=list[TemplateInfo])
async def list_templates() -> list[TemplateInfo]:
    return [
        TemplateInfo(key=t.key, title=t.title, description=t.description)
        for t in TEMPLATES.values()
    ]


@router.get("/sessions/{session_id}/notebook", response_model=list[NotebookCellOut])
async def get_notebook(
    session_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[NotebookCell]:
    await _get_ready_session_or_404(session_id, db)
    return await builder.get_cells(db, session_id)


@router.post(
    "/sessions/{session_id}/cells/{cell_id}/revert",
    response_model=list[NotebookCellOut],
)
async def revert_to_cell(
    session_id: str,
    cell_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    kernel_manager: Annotated[KernelManager, Depends(get_kernel_manager)],
) -> list[NotebookCell]:
    """MASTER_PROMPT.md §5.2 `revert_to_cell`/§7 "Revert to here": truncates the notebook after
    `cell_id` and shuts the kernel down so the *next* execution rebuilds it from the remaining
    cells (`app.notebook.seed.make_on_start_hook` replays every successful cell on kernel
    start). Only usable between agent runs — reverting mid-run would race the agent's own
    writes to the notebook and the kernel it's actively using."""
    session = await _get_ready_session_or_404(session_id, db)
    if session.agent_status in (AgentStatus.RUNNING, AgentStatus.WAITING_DECISION):
        raise HTTPException(
            status_code=409,
            detail="Can't revert while the agent is running or awaiting a decision.",
        )

    target = await db.get(NotebookCell, cell_id)
    if target is None or target.session_id != session_id:
        raise HTTPException(status_code=404, detail="Notebook cell not found")

    await db.execute(
        delete(NotebookCell).where(
            NotebookCell.session_id == session_id, NotebookCell.position > target.position
        )
    )
    await kernel_manager.shutdown_session(session_id)
    await db.commit()
    return await builder.get_cells(db, session_id)


@router.get("/sessions/{session_id}/kernel/status", response_model=KernelStatusOut)
async def kernel_status(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    kernel_manager: Annotated[KernelManager, Depends(get_kernel_manager)],
) -> KernelStatusOut:
    await _get_ready_session_or_404(session_id, db)
    return KernelStatusOut(status=kernel_manager.kernel_status(session_id))


@router.post(
    "/sessions/{session_id}/templates/{template_key}/run",
    response_model=list[NotebookCellOut],
)
async def run_template(
    session_id: str,
    template_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
    backend: Annotated[ExecutionBackend, Depends(get_execution_backend)],
    kernel_manager: Annotated[KernelManager, Depends(get_kernel_manager)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[NotebookCell]:
    session = await _get_ready_session_or_404(session_id, db)
    template = TEMPLATES.get(template_key)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Unknown template '{template_key}'")

    await builder.seed_notebook(db, session)
    await db.flush()

    try:
        await run_pending_seed_cells(session, db, storage, backend, kernel_manager, settings)
        new_cells, _summary = await render_and_run_template_step(
            db, session, storage, backend, kernel_manager, settings, template
        )
    except KernelStartupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.commit()
    return new_cells


@router.post("/sessions/{session_id}/notebook/export")
async def export_notebook(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
    backend: Annotated[ExecutionBackend, Depends(get_execution_backend)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_data: bool = False,
    include_pipeline: bool = False,
    include_exploratory: bool = False,
) -> Response:
    session = await _get_ready_session_or_404(session_id, db)
    all_cells = await builder.get_cells(db, session_id)
    # MASTER_PROMPT.md §6: exploratory Q&A cells (Phase 7, `NotebookCell.is_exploratory`) are
    # excluded by default, toggled in with `include_exploratory=true`. Excluded up front, before
    # the fresh-kernel validation below, so a broken exploratory cell never blocks export of an
    # otherwise-clean notebook the user didn't ask to include it in.
    cells = [c for c in all_cells if include_exploratory or not c.is_exploratory]
    code_cells = [c for c in cells if c.cell_type == CellType.CODE]

    validation_session_id = f"validate-{session.id}-{uuid4().hex[:8]}"
    dataset_bytes = storage.download(session.storage_key)
    try:
        handle = await backend.start_kernel(validation_session_id)
    except KernelStartupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        await backend.write_file(handle, f"data/{session.original_filename}", dataset_bytes)
        for cell in code_cells:
            result = await backend.execute(
                handle, cell.source, timeout=settings.kernel_cell_timeout_seconds
            )
            if result.status != "ok":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "The notebook failed to run top to bottom in a fresh kernel.",
                        "cell_id": cell.id,
                        "error": result.error_message,
                    },
                )
    finally:
        await backend.shutdown(handle)

    pipeline_bytes = (
        storage.download(session.pipeline_storage_key)
        if include_pipeline and session.pipeline_storage_key
        else None
    )
    zip_bytes = build_export_zip(
        session=session,
        cells=cells,
        kernel_requirements_text=read_kernel_requirements(),
        include_data=include_data,
        dataset_bytes=dataset_bytes if include_data else None,
        pipeline_bytes=pipeline_bytes,
    )
    filename = f"{session.original_filename.rsplit('.', 1)[0]}_datapilot_export.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
