"""Unit tests for app.analysis.templates.base's stdout-marker extraction.

MASTER_PROMPT.md §5.3 (`##DATAPILOT_SUMMARY##`) and §12 Phase 6 (`##DATAPILOT_PIPELINE##`,
`app.notebook.seed.render_and_run_template_step`'s pipeline-artifact persistence).
"""

import base64

from app.analysis.templates.base import extract_pipeline_artifact, extract_summary
from app.schemas.execution import ExecutionResult


def _result(text: str) -> ExecutionResult:
    return ExecutionResult(
        status="ok", outputs=[{"output_type": "stream", "name": "stdout", "text": text}]
    )


def test_extract_summary_parses_and_hides_the_marker_line() -> None:
    result = _result('visible output\n##DATAPILOT_SUMMARY##{"a": 1}\n')
    summary = extract_summary(result)
    assert summary == {"a": 1}
    assert result.outputs == [
        {"output_type": "stream", "name": "stdout", "text": "visible output\n"}
    ]


def test_extract_summary_returns_none_when_no_marker_present() -> None:
    result = _result("just some output\n")
    assert extract_summary(result) is None
    assert result.outputs[0]["text"] == "just some output\n"


def test_extract_summary_drops_a_stream_output_that_is_only_the_marker() -> None:
    result = _result('##DATAPILOT_SUMMARY##{"a": 1}\n')
    summary = extract_summary(result)
    assert summary == {"a": 1}
    assert result.outputs == []


def test_extract_pipeline_artifact_round_trips_bytes_and_hides_the_marker() -> None:
    payload = base64.b64encode(b"fake-joblib-bytes").decode("ascii")
    result = _result(f"other text\n##DATAPILOT_PIPELINE##{payload}\n")
    artifact = extract_pipeline_artifact(result)
    assert artifact == b"fake-joblib-bytes"
    assert result.outputs == [{"output_type": "stream", "name": "stdout", "text": "other text\n"}]


def test_extract_pipeline_artifact_returns_none_when_absent() -> None:
    result = _result("nothing relevant here\n")
    assert extract_pipeline_artifact(result) is None


def test_extract_summary_and_pipeline_artifact_compose_on_the_same_result() -> None:
    payload = base64.b64encode(b"pipeline-bytes").decode("ascii")
    result = _result(f'##DATAPILOT_PIPELINE##{payload}\n##DATAPILOT_SUMMARY##{{"ok": true}}\n')
    summary = extract_summary(result)
    artifact = extract_pipeline_artifact(result)
    assert summary == {"ok": True}
    assert artifact == b"pipeline-bytes"
    assert result.outputs == []
