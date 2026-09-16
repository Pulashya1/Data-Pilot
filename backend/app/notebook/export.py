"""`.ipynb` + zip export (MASTER_PROMPT.md §6, §12 Phase 2).

Fresh-kernel validation (re-running the notebook top to bottom before export) lives in the
API layer (`app/api/notebook.py`), since it needs the kernel manager; this module is a pure
transform from `NotebookCell` rows to bytes, which keeps it trivially unit-testable.
"""

import io
import zipfile
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output

from app.models.notebook import CellType, NotebookCell
from app.models.session import UploadSession

_KERNEL_REQUIREMENTS_PATH = (
    Path(__file__).resolve().parents[2] / "kernel_image" / "requirements.txt"
)


def read_kernel_requirements() -> str:
    return _KERNEL_REQUIREMENTS_PATH.read_text()


def cells_to_notebook(cells: list[NotebookCell]) -> nbformat.NotebookNode:
    nb_cells = []
    for cell in cells:
        if cell.cell_type == CellType.MARKDOWN:
            nb_cells.append(new_markdown_cell(cell.source))
            continue
        nb_cell = new_code_cell(cell.source, execution_count=cell.execution_count)
        for output in cell.outputs or []:
            kwargs = {k: v for k, v in output.items() if k != "output_type"}
            nb_cell["outputs"].append(new_output(output["output_type"], **kwargs))
        nb_cells.append(nb_cell)

    notebook = new_notebook(cells=nb_cells)
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python"}
    return notebook


def _stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0] if "." in filename else filename


def build_export_zip(
    *,
    session: UploadSession,
    cells: list[NotebookCell],
    kernel_requirements_text: str,
    include_data: bool,
    dataset_bytes: bytes | None,
    pipeline_bytes: bytes | None = None,
) -> bytes:
    """`pipeline_bytes` (MASTER_PROMPT.md §5.2 `export(format=pipeline_joblib)`, §6 "the exported
    pipeline code", §12 Phase 6) is the joblib-serialized fitted preprocessing `Pipeline` from
    the last successful `feature_engineering` cell, fetched by the caller
    (`app/api/notebook.py`) from `session.pipeline_storage_key`. `None` (no pipeline has been
    built yet, or the caller didn't ask for one) simply omits `pipeline.joblib` from the zip."""
    notebook = cells_to_notebook(cells)
    ipynb_text = nbformat.writes(notebook)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{_stem(session.original_filename)}.ipynb", ipynb_text)
        zf.writestr("requirements.txt", kernel_requirements_text)

        readme = f"This notebook expects `{session.original_filename}` in this directory.\n"
        if include_data and dataset_bytes is not None:
            zf.writestr(f"data/{session.original_filename}", dataset_bytes)
            readme += "The original dataset is included in this export.\n"
        else:
            readme += "The dataset was not included in this export; add your own copy here.\n"
        zf.writestr("data/README.md", readme)

        if pipeline_bytes is not None:
            zf.writestr("pipeline.joblib", pipeline_bytes)

    return buffer.getvalue()
