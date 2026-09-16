"""Unit tests for app.notebook.export (pure transform, no kernel)."""

import zipfile
from io import BytesIO

import nbformat

from app.models.notebook import CellStatus, CellType, NotebookCell
from app.models.session import FileType, SessionStatus, UploadSession
from app.notebook.export import build_export_zip, cells_to_notebook, read_kernel_requirements


def _cells() -> list[NotebookCell]:
    return [
        NotebookCell(
            id="c1",
            session_id="s1",
            position=0,
            cell_type=CellType.MARKDOWN,
            source="# Title",
            status=CellStatus.SUCCESS,
        ),
        NotebookCell(
            id="c2",
            session_id="s1",
            position=1,
            cell_type=CellType.CODE,
            source="print('hi')",
            execution_count=1,
            status=CellStatus.SUCCESS,
            outputs=[{"output_type": "stream", "name": "stdout", "text": "hi\n"}],
        ),
    ]


def _session() -> UploadSession:
    return UploadSession(
        id="s1",
        original_filename="sales.csv",
        storage_key="s1/sales.csv",
        file_type=FileType.CSV,
        size_bytes=10,
        status=SessionStatus.READY,
    )


def test_cells_to_notebook_is_valid_nbformat() -> None:
    notebook = cells_to_notebook(_cells())
    nbformat.validate(notebook)
    assert notebook["cells"][0]["cell_type"] == "markdown"
    assert notebook["cells"][1]["cell_type"] == "code"
    assert notebook["cells"][1]["outputs"][0]["text"] == "hi\n"


def test_read_kernel_requirements_is_nonempty() -> None:
    text = read_kernel_requirements()
    assert "ipykernel" in text


def test_build_export_zip_without_data() -> None:
    zip_bytes = build_export_zip(
        session=_session(),
        cells=_cells(),
        kernel_requirements_text="pandas==2.2.3\n",
        include_data=False,
        dataset_bytes=None,
    )
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "sales.ipynb" in names
        assert "requirements.txt" in names
        assert "data/README.md" in names
        assert "data/sales.csv" not in names


def test_build_export_zip_with_data() -> None:
    zip_bytes = build_export_zip(
        session=_session(),
        cells=_cells(),
        kernel_requirements_text="pandas==2.2.3\n",
        include_data=True,
        dataset_bytes=b"a,b\n1,2\n",
    )
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        assert "data/sales.csv" in zf.namelist()
        assert zf.read("data/sales.csv") == b"a,b\n1,2\n"


def test_build_export_zip_with_pipeline() -> None:
    zip_bytes = build_export_zip(
        session=_session(),
        cells=_cells(),
        kernel_requirements_text="pandas==2.2.3\n",
        include_data=False,
        dataset_bytes=None,
        pipeline_bytes=b"not-really-a-joblib-file",
    )
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        assert "pipeline.joblib" in zf.namelist()
        assert zf.read("pipeline.joblib") == b"not-really-a-joblib-file"
