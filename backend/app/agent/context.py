"""Compact, structured grounding context for LLM calls (MASTER_PROMPT.md §5.5, §12 Phase 3).

Never sends the full dataset: schema + per-column stats (already computed in Phase 1's
`DatasetProfile`) plus at most `sample_rows` preview rows, all as one JSON blob. JSON rather
than prose both keeps tokens down and gives `LLM_MODEL=mock` (`app/agent/llm.py`) something
precise to parse back out.
"""

import json
from typing import Any

from app.agent.semantic_types import infer_semantic_types
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
