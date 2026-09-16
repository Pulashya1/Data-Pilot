"""Notebook, template, and kernel endpoints (MASTER_PROMPT.md §8, §12 Phase 2).

No LLM involved: templates are rendered deterministically (app/analysis/templates) and run
in the session's sandboxed kernel (app/execution). The agent (Phase 3+) will drive these
same building blocks instead of explicit UI buttons.
"""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.templates.base import extract_summary
from app.analysis.templates.registry import TEMPLATES
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.storage import StorageBackend, get_storage_backend
from app.execution.backend import ExecutionBackend, KernelHandle, KernelStartupError
from app.execution.kernel_manager import (
    KernelManager,
    OnStartHook,
    get_execution_backend,
    get_kernel_manager,
)
from app.models.notebook import CellStatus, CellType, NotebookCell
from app.models.session import SessionStatus, UploadSession
from app.notebook import builder
from app.notebook.export import build_export_zip, read_kernel_requirements
from app.schemas.dataset import DatasetProfile
from app.schemas.notebook import KernelStatusOut, NotebookCellOut, TemplateInfo

router = APIRouter(tags=["notebook"])


async def _get_ready_session_or_404(session_id: str, db: AsyncSession) -> UploadSession:
    session = await db.get(UploadSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.READY or session.profile is None:
        raise HTTPException(status_code=409, detail="Session is not ready for analysis")
    return session


def _make_on_start_hook(
    session: UploadSession,
    db: AsyncSession,
    storage: StorageBackend,
    backend: ExecutionBackend,
    settings: Settings,
) -> OnStartHook:
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


async def _run_pending_seed_cells(
    session: UploadSession,
    db: AsyncSession,
    storage: StorageBackend,
    backend: ExecutionBackend,
    kernel_manager: KernelManager,
    settings: Settings,
) -> None:
    """Run any not-yet-executed seed cells (imports/config/data load) before new work."""
    on_start: OnStartHook | None = _make_on_start_hook(session, db, storage, backend, settings)
    cells = await builder.get_cells(db, session.id)
    for cell in cells:
        if cell.cell_type != CellType.CODE or cell.status != CellStatus.PENDING:
            continue
        result = await kernel_manager.run_cell(session.id, cell.source, on_start=on_start)
        on_start = None  # only needed once, to seed a brand-new kernel
        extract_summary(result)
        builder.apply_execution_result(cell, result)
        await db.flush()


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

    profile = DatasetProfile.model_validate(session.profile)
    await builder.seed_notebook(db, session)
    await db.flush()

    try:
        await _run_pending_seed_cells(session, db, storage, backend, kernel_manager, settings)
    except KernelStartupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    code = template.render(template.default_params(profile))
    cell = await builder.add_code_cell(db, session.id, code, label=template.title)
    await db.flush()

    on_start = _make_on_start_hook(session, db, storage, backend, settings)
    try:
        result = await kernel_manager.run_cell(session.id, code, on_start=on_start)
    except KernelStartupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    summary = extract_summary(result)
    builder.apply_execution_result(cell, result)
    await db.commit()

    new_cells: list[NotebookCell] = [cell]
    if summary is not None:
        insights = template.summarize(summary)
        if insights:
            markdown = "**Insights:**\n\n" + "\n".join(f"- {line}" for line in insights)
            insight_cell = await builder.add_markdown_cell(db, session.id, markdown)
            await db.commit()
            new_cells.append(insight_cell)
    return new_cells


@router.post("/sessions/{session_id}/notebook/export")
async def export_notebook(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
    backend: Annotated[ExecutionBackend, Depends(get_execution_backend)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_data: bool = False,
) -> Response:
    session = await _get_ready_session_or_404(session_id, db)
    cells = await builder.get_cells(db, session_id)
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

    zip_bytes = build_export_zip(
        session=session,
        cells=cells,
        kernel_requirements_text=read_kernel_requirements(),
        include_data=include_data,
        dataset_bytes=dataset_bytes if include_data else None,
    )
    filename = f"{session.original_filename.rsplit('.', 1)[0]}_datapilot_export.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
