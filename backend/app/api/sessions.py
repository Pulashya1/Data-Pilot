"""Session upload, profiling, listing, and preview endpoints (MASTER_PROMPT.md §8, Phase 1)."""

import io
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_session
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.core.storage import StorageBackend, get_storage_backend
from app.data.loaders import (
    FileParseError,
    LoadResult,
    NeedsSheetSelectionError,
    UnsupportedFileTypeError,
    detect_file_type,
    load_dataset,
)
from app.data.profiling import build_profile, rows_to_json_safe
from app.models.session import FileType, SessionStatus, UploadSession
from app.models.user import User
from app.schemas.dataset import DatasetProfile
from app.schemas.session import (
    PreviewResponse,
    SessionDetail,
    SessionSettingsRequest,
    SessionSummary,
    SheetSelectionRequest,
)

router = APIRouter(prefix="/sessions", tags=["sessions"], dependencies=[Depends(rate_limit)])

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    base = _UNSAFE_FILENAME_CHARS.sub("_", base).strip("._") or "upload"
    return base[:200]


async def _read_upload(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            raise HTTPException(status_code=413, detail="File exceeds the maximum upload size.")
        chunks.append(chunk)
    return b"".join(chunks)


def _ingest(
    raw: bytes, file_type: FileType, sheet_name: str | None, settings: Settings
) -> tuple[LoadResult, DatasetProfile, list[dict[str, object]]]:
    result = load_dataset(
        raw,
        file_type,
        sheet_name=sheet_name,
        sample_threshold=settings.sample_row_threshold,
        sample_size=settings.sample_size,
    )
    profile = build_profile(
        result.df,
        total_rows=result.total_rows,
        is_sampled=result.is_sampled,
        sample_size=result.sample_size,
    )
    preview_df = result.df.head(settings.preview_row_limit)
    preview_rows = rows_to_json_safe(preview_df)
    return result, profile, preview_rows


@router.post("", response_model=SessionDetail, status_code=201)
async def create_session(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> UploadSession:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required.")

    try:
        file_type = detect_file_type(file.filename)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw = await _read_upload(file, settings.max_upload_size_mb * 1024 * 1024)
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    safe_name = _sanitize_filename(file.filename)
    session = UploadSession(
        user_id=user.id,
        original_filename=safe_name,
        storage_key="",
        file_type=file_type,
        mime_type=file.content_type,
        size_bytes=len(raw),
        status=SessionStatus.UPLOADED,
    )
    db.add(session)
    await db.flush()

    session.storage_key = f"{session.id}/{safe_name}"
    storage.upload(
        session.storage_key, io.BytesIO(raw), file.content_type or "application/octet-stream"
    )

    try:
        _, profile, preview_rows = _ingest(raw, file_type, None, settings)
    except NeedsSheetSelectionError as exc:
        session.status = SessionStatus.NEEDS_SHEET_SELECTION
        session.sheet_names = exc.sheet_names
        await db.commit()
        return session
    except FileParseError as exc:
        session.status = SessionStatus.ERROR
        session.error_message = str(exc)
        await db.commit()
        return session

    session.status = SessionStatus.READY
    session.profile = profile.model_dump()
    session.preview_rows = preview_rows
    session.row_count = profile.n_rows
    session.column_count = profile.n_columns
    if file_type == FileType.EXCEL:
        session.selected_sheet = session.sheet_names[0] if session.sheet_names else None
    await db.commit()
    return session


@router.post("/{session_id}/sheet", response_model=SessionDetail)
async def select_sheet(
    body: SheetSelectionRequest,
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadSession:
    if session.status != SessionStatus.NEEDS_SHEET_SELECTION:
        raise HTTPException(status_code=409, detail="Session is not awaiting a sheet selection.")
    if not session.sheet_names or body.sheet_name not in session.sheet_names:
        raise HTTPException(status_code=400, detail=f"Unknown sheet '{body.sheet_name}'.")

    raw = storage.download(session.storage_key)
    try:
        _, profile, preview_rows = _ingest(raw, session.file_type, body.sheet_name, settings)
    except FileParseError as exc:
        session.status = SessionStatus.ERROR
        session.error_message = str(exc)
        await db.commit()
        return session

    session.status = SessionStatus.READY
    session.selected_sheet = body.sheet_name
    session.profile = profile.model_dump()
    session.preview_rows = preview_rows
    session.row_count = profile.n_rows
    session.column_count = profile.n_columns
    await db.commit()
    return session


@router.post("/{session_id}/settings", response_model=SessionDetail)
async def update_session_settings(
    body: SessionSettingsRequest,
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadSession:
    """MASTER_PROMPT.md §5.4/§7: the per-session "let the agent decide" toggle, and (Phase 7)
    the expertise level `app.agent.qa` adapts its answers to. Only affects decisions reached
    *after* this call — one already paused and awaiting the user keeps waiting for an explicit
    answer rather than silently auto-resolving. Both fields are optional so either can be set
    independently."""
    if body.auto_decide is not None:
        session.auto_decide = body.auto_decide
    if body.expertise_level is not None:
        session.expertise_level = body.expertise_level
    await db.commit()
    return session


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[UploadSession]:
    result = await db.execute(
        select(UploadSession)
        .where(UploadSession.user_id == user.id)
        .order_by(UploadSession.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session: Annotated[UploadSession, Depends(get_owned_session)],
) -> UploadSession:
    return session


@router.get("/{session_id}/preview", response_model=PreviewResponse)
async def preview_session(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    offset: int = 0,
    limit: int = 100,
) -> PreviewResponse:
    rows = session.preview_rows or []
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return PreviewResponse(
        total_available=len(rows), offset=offset, limit=limit, rows=rows[offset : offset + limit]
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session: Annotated[UploadSession, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
) -> None:
    if session.storage_key:
        storage.delete(session.storage_key)
    await db.delete(session)
    await db.commit()
