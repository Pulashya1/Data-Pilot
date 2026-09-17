"""Compact, structured grounding context for LLM calls (MASTER_PROMPT.md §5.5, §12 Phase 3/7).

Never sends the full dataset: schema + per-column stats (already computed in Phase 1's
`DatasetProfile`) plus at most `sample_rows` preview rows, all as one JSON blob. JSON rather
than prose both keeps tokens down and gives `LLM_MODEL=mock` (`app/agent/llm.py`) something
precise to parse back out.
"""

import json
from typing import Any

from app.agent.semantic_types import infer_semantic_types
from app.models.notebook import NotebookCell
from app.schemas.dataset import DatasetProfile


def build_understand_context(
    profile: DatasetProfile,
    preview_rows: list[dict[str, Any]],
    sample_rows: int,
) -> str:
    semantic_types = infer_semantic_types(profile)
    columns = [
        {
            "name": col.name,
            "dtype": col.dtype,
            "semantic_type": semantic_types[col.name],
            "unique_count": col.unique_count,
            "missing_pct": col.missing_pct,
            "numeric_stats": col.numeric_stats,
            "top_values": [tv.value for tv in (col.top_values or [])][:5],
        }
        for col in profile.columns
    ]
    payload = {
        "n_rows": profile.n_rows,
        "n_columns": profile.n_columns,
        "is_sampled": profile.is_sampled,
        "columns": columns,
        "sample_rows": preview_rows[: max(sample_rows, 0)],
    }
    return json.dumps(payload, default=str)


def _cell_output_summary(cell: NotebookCell, max_chars: int) -> str:
    """Flattens a cell's outputs to plain text for an LLM prompt (§5.5: "truncated cell
    outputs, a maximum number of characters per output") — figures are skipped, not described,
    since there's no image-understanding call in this project's design (§5.5: figures are
    described via their underlying numbers, not images, and this project makes zero paid LLM
    calls, so no vision model is available either)."""
    if cell.error_message:
        return f"ERROR: {cell.error_message}"[:max_chars]
    parts = []
    for output in cell.outputs or []:
        if output.get("output_type") == "stream":
            parts.append(str(output.get("text", "")))
        elif output.get("output_type") in ("execute_result", "display_data"):
            data = output.get("data")
            text = data.get("text/plain") if isinstance(data, dict) else None
            if isinstance(text, str):
                parts.append(text)
    joined = "\n".join(p for p in parts if p).strip()
    return joined[:max_chars]


def build_qa_context(
    *,
    question: str,
    expertise_level: str,
    problem_type: str | None,
    target_column: str | None,
    profile: DatasetProfile,
    referenced_cells: list[NotebookCell],
    recent_insight_bullets: list[str],
    decisions: list[dict[str, Any]],
    max_output_chars: int,
) -> str:
    """MASTER_PROMPT.md §5.6: grounds a Q&A answer in the actual notebook, never the raw
    dataset. `referenced_cells` (parsed from `@cell-<position>` in the question by
    `app.agent.qa`) take priority; `recent_insight_bullets` fill in when the user didn't point
    at a specific cell, so a generic question still has *something* concrete to ground on."""
    payload = {
        "question": question,
        "expertise_level": expertise_level,
        "problem_type": problem_type,
        "target_column": target_column,
        "column_names": [c.name for c in profile.columns],
        "n_rows": profile.n_rows,
        "referenced_cells": [
            {
                "position": cell.position,
                "cell_type": cell.cell_type.value,
                "label": cell.label,
                "status": cell.status.value,
                "source": cell.source[:max_output_chars],
                "output_summary": _cell_output_summary(cell, max_output_chars),
            }
            for cell in referenced_cells
        ],
        "recent_insights": recent_insight_bullets[-10:] if not referenced_cells else [],
        "decisions": decisions,
    }
    return json.dumps(payload, default=str)
