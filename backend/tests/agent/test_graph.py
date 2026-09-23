"""End-to-end LangGraph agent run tests (MASTER_PROMPT.md §5.1, §12 Phase 3/4).

Runs the full ingest -> understand -> plan -> execute_step -> summarize graph through the API,
with `LLM_MODEL=mock` (the test-suite default, from `Settings`) and `FakeExecutionBackend` (no
Docker). Nothing here overrides `llm_model`, so this also guards CI's "never call a real LLM"
invariant.

Phase 4 changed the default: a session now *pauses* (`agent_status=waiting_decision`) at the
target-confirmation and plan-approval decision points unless `auto_decide` is turned on for that
session (`POST /sessions/{id}/settings`). Tests that want the old full-auto-run behavior enable
it explicitly; the rest exercise the real pause/answer/resume flow.
"""

import io
import json
import time
import zipfile
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision import Decision

SAMPLE_DF = pd.DataFrame(
    {
        "id": range(1, 41),
        "age": [20 + (i % 40) for i in range(40)],
        "income": [30_000 + 500 * i for i in range(40)],
        "churned": [i % 3 == 0 for i in range(40)],
    }
)


def _upload(client: TestClient) -> str:
    csv_bytes = SAMPLE_DF.to_csv(index=False).encode()
    response = client.post(
        "/sessions", files={"file": ("customers.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert response.status_code == 201
    return response.json()["id"]  # type: ignore[no-any-return]


def _upload_with_auto_decide(client: TestClient) -> str:
    session_id = _upload(client)
    response = client.post(f"/sessions/{session_id}/settings", json={"auto_decide": True})
    assert response.status_code == 200
    assert response.json()["auto_decide"] is True
    return session_id


def _wait_for_status(
    client: TestClient, session_id: str, statuses: tuple[str, ...], timeout: float = 60.0
) -> dict[str, Any]:
    # Generous on purpose: the loop returns as soon as the status is reached, but the first full
    # run in a test session pays for cold imports (sklearn, shap, statsmodels) inside the fake
    # kernel, which can take well over 20s on a slow CI runner.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        session = client.get(f"/sessions/{session_id}").json()
        if session["agent_status"] in statuses:
            return session  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError(f"agent did not reach {statuses} in time")


def _wait_for_agent(client: TestClient, session_id: str, timeout: float = 60.0) -> dict[str, Any]:
    return _wait_for_status(client, session_id, ("done", "error"), timeout=timeout)


def _pending_decision(client: TestClient, session_id: str, kind: str) -> dict[str, Any]:
    decisions = client.get(f"/sessions/{session_id}/decisions").json()
    matches = [d for d in decisions if d["kind"] == kind and d["selected_option"] is None]
    assert matches, f"no pending {kind} decision; got {decisions}"
    return matches[0]


def test_agent_runs_end_to_end_and_picks_a_target(client: TestClient) -> None:
    session_id = _upload_with_auto_decide(client)

    start = client.post(f"/sessions/{session_id}/agent/start")
    assert start.status_code == 202

    session = _wait_for_agent(client, session_id)
    assert session["agent_status"] == "done", session.get("agent_error_message")
    assert session["target_column"] == "churned"
    assert session["problem_type"] == "binary_classification"
    assert session["plan_steps"]

    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    labels = [c["label"] for c in notebook if c["cell_type"] == "code"]
    assert "Imports" in labels
    assert any(label == "Missing values" for label in labels)

    markdown_sources = [c["source"] for c in notebook if c["cell_type"] == "markdown"]
    assert any(s.startswith("## Problem type & target") for s in markdown_sources)
    assert any(s.startswith("## Summary") for s in markdown_sources)


async def test_agent_run_records_decisions(client: TestClient, db_session: AsyncSession) -> None:
    session_id = _upload_with_auto_decide(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_agent(client, session_id)

    result = await db_session.execute(select(Decision).where(Decision.session_id == session_id))
    decisions = result.scalars().all()
    kinds = {d.kind.value for d in decisions}
    assert kinds == {
        "target_confirmation",
        "plan_approval",
        "feature_engineering_approval",
        "baseline_approval",
    }
    assert all(d.auto_decided for d in decisions)


def test_cannot_start_agent_twice_while_running(client: TestClient) -> None:
    session_id = _upload_with_auto_decide(client)
    first = client.post(f"/sessions/{session_id}/agent/start")
    assert first.status_code == 202
    second = client.post(f"/sessions/{session_id}/agent/start")
    assert second.status_code == 409
    _wait_for_agent(client, session_id)


def test_start_agent_on_unknown_session_404(client: TestClient) -> None:
    response = client.post("/sessions/does-not-exist/agent/start")
    assert response.status_code == 404


def test_usage_reports_zero_real_calls_in_mock_mode(client: TestClient) -> None:
    session_id = _upload_with_auto_decide(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_agent(client, session_id)

    usage = client.get(f"/sessions/{session_id}/usage").json()
    assert usage["calls_used"] == 0


def test_agent_pauses_for_target_confirmation_by_default(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")

    session = _wait_for_status(client, session_id, ("waiting_decision", "error"))
    assert session["agent_status"] == "waiting_decision", session.get("agent_error_message")
    assert session["target_column"] is None

    decision = _pending_decision(client, session_id, "target_confirmation")
    assert decision["recommended_option"] == "churned"
    assert "churned" in decision["options"]
    assert "(no target)" in decision["options"]


def test_answering_target_confirmation_resumes_to_plan_approval(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))

    decision = _pending_decision(client, session_id, "target_confirmation")
    answer = client.post(
        f"/sessions/{session_id}/decisions/{decision['id']}",
        json={"selected_option": "churned"},
    )
    assert answer.status_code == 200
    assert answer.json()["selected_option"] == "churned"

    session = _wait_for_status(client, session_id, ("waiting_decision", "error"))
    assert session["agent_status"] == "waiting_decision", session.get("agent_error_message")
    assert session["target_column"] == "churned"
    assert session["problem_type"] == "binary_classification"

    plan_decision = _pending_decision(client, session_id, "plan_approval")
    assert "missing_values" in plan_decision["options"]


def test_overriding_target_recomputes_problem_type_without_a_second_llm_call(
    client: TestClient,
) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    decision = _pending_decision(client, session_id, "target_confirmation")

    answer = client.post(
        f"/sessions/{session_id}/decisions/{decision['id']}",
        json={"selected_option": "(no target)"},
    )
    assert answer.status_code == 200

    session = _wait_for_status(client, session_id, ("waiting_decision", "error"))
    assert session["target_column"] is None
    assert session["problem_type"] is None
    assert client.get(f"/sessions/{session_id}/usage").json()["calls_used"] == 0


def test_rejecting_an_unknown_target_answer_400s(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    decision = _pending_decision(client, session_id, "target_confirmation")

    response = client.post(
        f"/sessions/{session_id}/decisions/{decision['id']}",
        json={"selected_option": "not_a_real_column"},
    )
    assert response.status_code == 400


def test_editing_the_plan_drops_and_reorders_steps(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    target_decision = _pending_decision(client, session_id, "target_confirmation")
    client.post(
        f"/sessions/{session_id}/decisions/{target_decision['id']}",
        json={"selected_option": "churned"},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))

    edited = client.post(
        f"/sessions/{session_id}/plan", json={"steps": ["correlations", "duplicates"]}
    )
    assert edited.status_code == 200
    assert edited.json()["selected_option"] == "correlations,duplicates"

    # Phase 6: feature_engineering_approval and baseline_approval (target is confirmed and
    # binary_classification, so both are asked) also pause since auto_decide is off here.
    _wait_for_status(client, session_id, ("waiting_decision",))
    fe_decision = _pending_decision(client, session_id, "feature_engineering_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{fe_decision['id']}",
        json={"selected_option": "recommended"},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))
    baseline_decision = _pending_decision(client, session_id, "baseline_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{baseline_decision['id']}",
        json={"selected_option": "yes"},
    )

    session = _wait_for_agent(client, session_id)
    assert session["agent_status"] == "done", session.get("agent_error_message")
    assert session["plan_steps"] == ["correlations", "duplicates"]

    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    labels = {c["label"] for c in notebook if c["cell_type"] == "code"}
    assert "Missing values" not in labels
    assert "Correlations & multicollinearity" in labels


def test_plan_edit_with_unknown_step_400s(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    target_decision = _pending_decision(client, session_id, "target_confirmation")
    client.post(
        f"/sessions/{session_id}/decisions/{target_decision['id']}",
        json={"selected_option": "churned"},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))

    response = client.post(f"/sessions/{session_id}/plan", json={"steps": ["not_a_template"]})
    assert response.status_code == 400


def test_decisions_panel_lists_answered_and_pending(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))

    decisions = client.get(f"/sessions/{session_id}/decisions").json()
    assert len(decisions) == 1
    assert decisions[0]["selected_option"] is None
    assert decisions[0]["auto_decided"] is False


def test_double_answering_a_decision_409s(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    decision = _pending_decision(client, session_id, "target_confirmation")

    first = client.post(
        f"/sessions/{session_id}/decisions/{decision['id']}",
        json={"selected_option": "churned"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/sessions/{session_id}/decisions/{decision['id']}",
        json={"selected_option": "age"},
    )
    assert second.status_code == 409


# --- Phase 6: feature engineering & baseline (MASTER_PROMPT.md §5.1 steps 5/6, §12) ---------


def test_feature_engineering_and_baseline_run_with_auto_decide(client: TestClient) -> None:
    session_id = _upload_with_auto_decide(client)
    client.post(f"/sessions/{session_id}/agent/start")
    session = _wait_for_agent(client, session_id)
    assert session["agent_status"] == "done", session.get("agent_error_message")

    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    labels = [c["label"] for c in notebook if c["cell_type"] == "code"]
    assert "Feature engineering pipeline" in labels
    assert "Baseline model" in labels
    fe_cell = next(c for c in notebook if c["label"] == "Feature engineering pipeline")
    assert fe_cell["status"] == "success"
    baseline_cell = next(c for c in notebook if c["label"] == "Baseline model")
    assert baseline_cell["status"] == "success"

    decisions = client.get(f"/sessions/{session_id}/decisions").json()
    kinds = {d["kind"]: d for d in decisions}
    assert kinds["feature_engineering_approval"]["selected_option"] == "recommended"
    assert kinds["baseline_approval"]["selected_option"] == "yes"

    # The fitted pipeline artifact was persisted and is downloadable via export.
    export = client.post(f"/sessions/{session_id}/notebook/export?include_pipeline=true")
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as zf:
        assert "pipeline.joblib" in zf.namelist()
        assert len(zf.read("pipeline.joblib")) > 0


def test_export_without_include_pipeline_omits_the_artifact(client: TestClient) -> None:
    session_id = _upload_with_auto_decide(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_agent(client, session_id)

    export = client.post(f"/sessions/{session_id}/notebook/export")
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as zf:
        assert "pipeline.joblib" not in zf.namelist()


def _approve_through_plan(client: TestClient, session_id: str) -> None:
    """Answers target_confirmation (churned) then the recommended plan, for a session started
    without auto_decide, leaving it paused at `feature_engineering_approval` next."""
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    target_decision = _pending_decision(client, session_id, "target_confirmation")
    client.post(
        f"/sessions/{session_id}/decisions/{target_decision['id']}",
        json={"selected_option": "churned"},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))
    plan_decision = _pending_decision(client, session_id, "plan_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{plan_decision['id']}",
        json={"selected_option": plan_decision["recommended_option"]},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))


def test_declining_the_baseline_skips_it(client: TestClient) -> None:
    session_id = _upload(client)
    _approve_through_plan(client, session_id)
    fe_decision = _pending_decision(client, session_id, "feature_engineering_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{fe_decision['id']}",
        json={"selected_option": "recommended"},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))
    baseline_decision = _pending_decision(client, session_id, "baseline_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{baseline_decision['id']}",
        json={"selected_option": "no"},
    )

    session = _wait_for_agent(client, session_id)
    assert session["agent_status"] == "done", session.get("agent_error_message")

    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    labels = {c["label"] for c in notebook if c["cell_type"] == "code"}
    assert "Feature engineering pipeline" in labels
    assert "Baseline model" not in labels


def test_feature_engineering_json_override_is_applied(client: TestClient) -> None:
    session_id = _upload(client)
    _approve_through_plan(client, session_id)
    fe_decision = _pending_decision(client, session_id, "feature_engineering_approval")

    bad = client.post(
        f"/sessions/{session_id}/decisions/{fe_decision['id']}",
        json={"selected_option": "not json and not 'recommended'"},
    )
    assert bad.status_code == 400

    bad_key = client.post(
        f"/sessions/{session_id}/decisions/{fe_decision['id']}",
        json={"selected_option": json.dumps({"not_a_real_option": 1})},
    )
    assert bad_key.status_code == 400

    good = client.post(
        f"/sessions/{session_id}/decisions/{fe_decision['id']}",
        json={"selected_option": json.dumps({"scaling": "none", "numeric_impute": "mean"})},
    )
    assert good.status_code == 200

    _wait_for_status(client, session_id, ("waiting_decision", "done", "error"))
    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    fe_cell = next(c for c in notebook if c["label"] == "Feature engineering pipeline")
    assert "'mean'" in fe_cell["source"]
    assert fe_cell["status"] == "success"


def test_baseline_is_never_asked_without_a_target(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")
    _wait_for_status(client, session_id, ("waiting_decision",))
    target_decision = _pending_decision(client, session_id, "target_confirmation")
    client.post(
        f"/sessions/{session_id}/decisions/{target_decision['id']}",
        json={"selected_option": "(no target)"},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))
    plan_decision = _pending_decision(client, session_id, "plan_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{plan_decision['id']}",
        json={"selected_option": plan_decision["recommended_option"]},
    )
    _wait_for_status(client, session_id, ("waiting_decision",))
    fe_decision = _pending_decision(client, session_id, "feature_engineering_approval")
    client.post(
        f"/sessions/{session_id}/decisions/{fe_decision['id']}",
        json={"selected_option": "recommended"},
    )

    # No baseline_approval decision should ever appear — the graph goes straight to "done".
    session = _wait_for_agent(client, session_id)
    assert session["agent_status"] == "done", session.get("agent_error_message")
    decisions = client.get(f"/sessions/{session_id}/decisions").json()
    assert not any(d["kind"] == "baseline_approval" for d in decisions)
    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    labels = {c["label"] for c in notebook if c["cell_type"] == "code"}
    assert "Feature engineering pipeline" in labels
    assert "Baseline model" not in labels
