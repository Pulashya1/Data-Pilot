"""API-level tests for the agent run and SSE stream endpoints (MASTER_PROMPT.md §8, §12 Phase 3)."""

import io
import json

import pandas as pd
from fastapi.testclient import TestClient

SAMPLE_DF = pd.DataFrame(
    {
        "id": range(1, 21),
        "age": [20 + i for i in range(20)],
        "outcome": [i % 2 == 0 for i in range(20)],
    }
)


def _upload(client: TestClient) -> str:
    csv_bytes = SAMPLE_DF.to_csv(index=False).encode()
    response = client.post(
        "/sessions", files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert response.status_code == 201
    return response.json()["id"]  # type: ignore[no-any-return]


def test_agent_start_on_ready_session_202(client: TestClient) -> None:
    session_id = _upload(client)
    response = client.post(f"/sessions/{session_id}/agent/start")
    assert response.status_code == 202


def test_agent_start_on_unknown_session_404(client: TestClient) -> None:
    response = client.post("/sessions/does-not-exist/agent/start")
    assert response.status_code == 404


def test_stream_emits_events_and_closes_on_terminal_status(client: TestClient) -> None:
    # Phase 4: auto_decide is off by default, so the run pauses at the first decision point
    # (target confirmation) instead of reaching plan_update — see the SSE-per-decision test
    # below for the full pause/resume/close-again cycle.
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/settings", json={"auto_decide": True})
    client.post(f"/sessions/{session_id}/agent/start")

    with client.stream("GET", f"/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        event_types = []
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: ") :])
            event_types.append(event["type"])
            if event["type"] == "agent_status" and event["status"] in ("done", "error"):
                break

    assert "plan_update" in event_types
    assert "agent_status" in event_types
    assert event_types[-1] == "agent_status"


def test_stream_closes_when_agent_pauses_for_a_decision(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/agent/start")

    with client.stream("GET", f"/sessions/{session_id}/stream") as response:
        event_types = []
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: ") :])
            event_types.append(event["type"])
            if event["type"] == "agent_status" and event["status"] == "waiting_decision":
                break

    assert "decision" in event_types
    assert event_types[-1] == "agent_status"


def test_stream_on_unknown_session_404(client: TestClient) -> None:
    response = client.get("/sessions/does-not-exist/stream")
    assert response.status_code == 404


def test_usage_on_unknown_session_404(client: TestClient) -> None:
    response = client.get("/sessions/does-not-exist/usage")
    assert response.status_code == 404
