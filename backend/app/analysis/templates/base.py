"""Tested, parameterized analysis code templates (MASTER_PROMPT.md §5.3).

Standard analyses are template-generated, not LLM-generated — the agent (Phase 3+) will
just pick a template and fill in parameters, which keeps the project reliable on small free
models and minimizes tokens. Each rendered cell's last stdout line is a
`##DATAPILOT_SUMMARY##<json>` marker; `extract_summary` pulls it out of the kernel's real
output and strips it from what the user sees, and `Template.summarize` turns those exact
numbers into 2-4 insight bullets — so the insight text is always grounded in what the
kernel actually computed.
"""

import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.dataset import DatasetProfile
from app.schemas.execution import ExecutionResult

MARKER = "##DATAPILOT_SUMMARY##"


@dataclass
class Template:
    key: str
    title: str
    description: str
    render: Callable[[dict[str, Any]], str]
    summarize: Callable[[dict[str, Any]], list[str]]
    default_params: Callable[[DatasetProfile], dict[str, Any]]


def extract_summary(result: ExecutionResult) -> dict[str, Any] | None:
    """Split the summary marker out of stream outputs; returns the parsed summary (if any)
    and mutates nothing — callers should replace `result.outputs` with the cleaned list."""
    summary: dict[str, Any] | None = None
    cleaned: list[dict[str, Any]] = []
    for output in result.outputs:
        if output.get("output_type") != "stream":
            cleaned.append(output)
            continue
        kept_lines = []
        for line in output["text"].splitlines():
            if line.startswith(MARKER):
                with contextlib.suppress(json.JSONDecodeError):
                    summary = json.loads(line[len(MARKER) :])
                continue
            kept_lines.append(line)
        text = "\n".join(kept_lines)
        if text.strip():
            cleaned.append({**output, "text": text + "\n"})
    result.outputs = cleaned
    return summary


def numeric_columns(profile: DatasetProfile, limit: int = 12) -> list[str]:
    return [c.name for c in profile.columns if c.numeric_stats is not None][:limit]


def categorical_columns(profile: DatasetProfile, limit: int = 8) -> list[str]:
    return [c.name for c in profile.columns if c.numeric_stats is None][:limit]
