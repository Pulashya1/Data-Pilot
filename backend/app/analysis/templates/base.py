"""Tested, parameterized analysis code templates (MASTER_PROMPT.md §5.3).

Standard analyses are template-generated, not LLM-generated — the agent (Phase 3+) will
just pick a template and fill in parameters, which keeps the project reliable on small free
models and minimizes tokens. Each rendered cell's last stdout line is a
`##DATAPILOT_SUMMARY##<json>` marker; `extract_summary` pulls it out of the kernel's real
output and strips it from what the user sees, and `Template.summarize` turns those exact
numbers into 2-4 insight bullets — so the insight text is always grounded in what the
kernel actually computed.

`extract_pipeline_artifact` (Phase 6, MASTER_PROMPT.md §5.1 step 5, §5.2 `export`) reuses the
same stdout-marker mechanism for a second, optional payload: the `feature_engineering`
template base64-encodes its fitted `Pipeline` (joblib, in-memory — no container filesystem
access needed) behind a `##DATAPILOT_PIPELINE##` marker line. Every other template simply
never prints that marker, so this is a no-op for them.
"""

import base64
import binascii
import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.dataset import DatasetProfile
from app.schemas.execution import ExecutionResult

MARKER = "##DATAPILOT_SUMMARY##"
PIPELINE_MARKER = "##DATAPILOT_PIPELINE##"


@dataclass
class Template:
    key: str
    title: str
    description: str
    render: Callable[[dict[str, Any]], str]
    summarize: Callable[[dict[str, Any]], list[str]]
    default_params: Callable[[DatasetProfile], dict[str, Any]]


def _extract_marker_line(result: ExecutionResult, marker: str) -> str | None:
    """Strips every stdout line starting with `marker` out of `result.outputs` (mutated in
    place) and returns the last one's payload (the text after the marker), if any."""
    captured: str | None = None
    cleaned: list[dict[str, Any]] = []
    for output in result.outputs:
        if output.get("output_type") != "stream":
            cleaned.append(output)
            continue
        kept_lines = []
        for line in output["text"].splitlines():
            if line.startswith(marker):
                captured = line[len(marker) :]
                continue
            kept_lines.append(line)
        text = "\n".join(kept_lines)
        if text.strip():
            cleaned.append({**output, "text": text + "\n"})
    result.outputs = cleaned
    return captured


def extract_summary(result: ExecutionResult) -> dict[str, Any] | None:
    """Splits the `##DATAPILOT_SUMMARY##` marker line out of stream outputs and parses it;
    mutates `result.outputs` to hide the marker line from the user."""
    raw = _extract_marker_line(result, MARKER)
    if raw is None:
        return None
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(raw)  # type: ignore[no-any-return]
    return None


def extract_pipeline_artifact(result: ExecutionResult) -> bytes | None:
    """Splits the `##DATAPILOT_PIPELINE##` marker line (base64-encoded joblib bytes) out of
    stream outputs; mutates `result.outputs` to hide the marker line from the user. Must be
    called after `extract_summary` has already cleaned `result.outputs` once."""
    raw = _extract_marker_line(result, PIPELINE_MARKER)
    if raw is None:
        return None
    try:
        return base64.b64decode(raw, validate=True)
    except binascii.Error:
        return None


def numeric_columns(profile: DatasetProfile, limit: int = 12) -> list[str]:
    return [c.name for c in profile.columns if c.numeric_stats is not None][:limit]


def categorical_columns(profile: DatasetProfile, limit: int = 8) -> list[str]:
    return [c.name for c in profile.columns if c.numeric_stats is None][:limit]
