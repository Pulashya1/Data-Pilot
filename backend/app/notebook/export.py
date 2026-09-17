"""`.ipynb` + zip export, and a standalone HTML report export (MASTER_PROMPT.md §6, §8, §12
Phase 2/8).

Fresh-kernel validation (re-running the notebook top to bottom before export) lives in the
API layer (`app/api/notebook.py`), since it needs the kernel manager; this module is a pure
transform from `NotebookCell` rows to bytes, which keeps it trivially unit-testable.
"""

import html as html_lib
import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


# -- HTML report export (MASTER_PROMPT.md §8/§12 Phase 8) --------------------------------------
#
# No `nbconvert` dependency (not in MASTER_PROMPT.md §2's stack, and pulling in its jinja2/
# mistune/bleach/pygments chain for one report format isn't worth it — §13: ask before adding a
# library outside the spec). Markdown cells only ever come from this project's own templates/LLM
# (`app/agent/prompts/system.md` instructs plain, simple markdown — headers, bold, lists), so a
# small hand-rolled subset covers everything actually produced; a code viewer's syntax
# highlighting isn't attempted here either, same reasoning.

_MD_HEADER_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_CODE_RE = re.compile(r"`([^`]+)`")


def _inline_markdown(text: str) -> str:
    text = html_lib.escape(text)
    text = _MD_BOLD_RE.sub(r"<strong>\1</strong>", text)
    return _MD_CODE_RE.sub(r"<code>\1</code>", text)


def _markdown_to_html(source: str) -> str:
    """A deliberately small subset: `#`..`####` headers, `**bold**`, `` `code` ``, `- ` bullet
    lists, and blank-line-separated paragraphs — everything `app/agent/prompts/system.md` and
    the analysis templates (`app/analysis/templates/base.py::Template.summarize`) actually
    produce."""
    lines_out: list[str] = []
    list_open = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            lines_out.append(f"<p>{' '.join(paragraph)}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            lines_out.append("</ul>")
            list_open = False

    for raw_line in source.splitlines():
        line = raw_line.rstrip()
        header_match = _MD_HEADER_RE.match(line)
        if header_match:
            flush_paragraph()
            close_list()
            level = len(header_match.group(1))
            lines_out.append(f"<h{level}>{_inline_markdown(header_match.group(2))}</h{level}>")
        elif line.startswith("- "):
            flush_paragraph()
            if not list_open:
                lines_out.append("<ul>")
                list_open = True
            lines_out.append(f"<li>{_inline_markdown(line[2:])}</li>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            paragraph.append(_inline_markdown(line))

    flush_paragraph()
    close_list()
    return "\n".join(lines_out)


def _render_output_html(output: dict[str, Any]) -> str:
    output_type = output.get("output_type")
    if output_type == "stream":
        return f'<pre class="output">{html_lib.escape(output.get("text", ""))}</pre>'
    if output_type == "error":
        traceback_text = "\n".join(output.get("traceback") or [])
        return f'<pre class="output error">{html_lib.escape(traceback_text)}</pre>'
    if output_type in ("execute_result", "display_data"):
        data = output.get("data", {})
        if "image/png" in data:
            return f'<img class="output-image" src="data:image/png;base64,{data["image/png"]}">'
        if "text/html" in data:
            # Only ever produced by this project's own kernel-rendered pandas/plotly output —
            # never user- or LLM-authored HTML — so embedding it unescaped is safe here.
            html_value = data["text/html"]
            return "\n".join(html_value) if isinstance(html_value, list) else str(html_value)
        if "text/plain" in data:
            text_value = data["text/plain"]
            text = "".join(text_value) if isinstance(text_value, list) else text_value
            return f'<pre class="output">{html_lib.escape(text)}</pre>'
    return ""


_REPORT_STYLE = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 900px;
       margin: 2rem auto; padding: 0 1.5rem; color: #1a1a1a; line-height: 1.5; }
h1 { border-bottom: 2px solid #e5e5e5; padding-bottom: 0.5rem; }
.meta { color: #666; font-size: 0.9rem; margin-bottom: 2rem; }
.cell { margin-bottom: 1.25rem; }
.code { background: #f6f8fa; border-radius: 6px; padding: 0.75rem 1rem; overflow-x: auto;
        font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem; white-space: pre-wrap; }
.output { background: #fbfbfb; border-left: 3px solid #d0d7de; padding: 0.5rem 1rem;
          overflow-x: auto; font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem;
          white-space: pre-wrap; }
.output.error { border-left-color: #cf222e; color: #cf222e; }
.output-image { max-width: 100%; border-radius: 6px; margin: 0.5rem 0; }
ul { margin: 0.5rem 0; }
"""


def render_notebook_html(session: UploadSession, cells: list[NotebookCell]) -> str:
    """A single self-contained HTML report (MASTER_PROMPT.md §8 `export(format=html)`) — no
    external assets, so it opens correctly as a downloaded file with no server behind it."""
    parts: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{html_lib.escape(session.original_filename)} — DataPilot report</title>",
        f"<style>{_REPORT_STYLE}</style></head><body>",
        f"<h1>{html_lib.escape(session.original_filename)}</h1>",
        '<div class="meta">Generated by DataPilot on '
        f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        + (f" · Problem type: {session.problem_type.value}" if session.problem_type else "")
        + (f" · Target: {html_lib.escape(session.target_column)}" if session.target_column else "")
        + "</div>",
    ]
    for cell in cells:
        parts.append('<div class="cell">')
        if cell.cell_type == CellType.MARKDOWN:
            parts.append(_markdown_to_html(cell.source))
        else:
            parts.append(f'<pre class="code">{html_lib.escape(cell.source)}</pre>')
            for output in cell.outputs or []:
                parts.append(_render_output_html(output))
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)
