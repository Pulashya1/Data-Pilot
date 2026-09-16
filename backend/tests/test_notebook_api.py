"""API-level tests for templates/notebook/export, using FakeExecutionBackend (no Docker)."""

import io
import zipfile

import pandas as pd
from fastapi.testclient import TestClient

from app.execution.kernel_manager import KernelManager
from tests.fakes import FakeExecutionBackend

SAMPLE_DF = pd.DataFrame(
    {
        "id": range(1, 21),
        "age": [20 + i for i in range(20)],
        "score": [1.0, 2.0, 3.0, None, 5.0] * 4,
    }
)


def _upload(client: TestClient) -> str:
    csv_bytes = SAMPLE_DF.to_csv(index=False).encode()
    response = client.post(
        "/sessions", files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert response.status_code == 201
    return response.json()["id"]  # type: ignore[no-any-return]


def test_list_templates_returns_the_core_set(client: TestClient) -> None:
    response = client.get("/templates")
    assert response.status_code == 200
    keys = {t["key"] for t in response.json()}
    assert keys == {
        "overview",
        "missing_values",
        "duplicates",
        "constant_and_id_columns",
        "univariate_distributions",
        "outliers",
        "correlations",
    }


def test_run_template_seeds_notebook_and_appends_cells(client: TestClient) -> None:
    session_id = _upload(client)

    response = client.post(f"/sessions/{session_id}/templates/missing_values/run")
    assert response.status_code == 200
    new_cells = response.json()
    assert new_cells[0]["cell_type"] == "code"
    assert new_cells[0]["status"] == "success"
    assert new_cells[-1]["cell_type"] == "markdown"

    notebook = client.get(f"/sessions/{session_id}/notebook").json()
    labels = [c["label"] for c in notebook if c["cell_type"] == "code"]
    assert labels == ["Imports", "Configuration", "Load data", "Missing values"]


def test_run_template_twice_reuses_the_kernel(
    client: TestClient, fake_execution_backend: FakeExecutionBackend
) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/templates/overview/run")
    client.post(f"/sessions/{session_id}/templates/duplicates/run")
    assert fake_execution_backend.start_count == 1


def test_run_unknown_template_404(client: TestClient) -> None:
    session_id = _upload(client)
    response = client.post(f"/sessions/{session_id}/templates/does-not-exist/run")
    assert response.status_code == 404


def test_run_template_on_missing_session_404(client: TestClient) -> None:
    response = client.post("/sessions/does-not-exist/templates/overview/run")
    assert response.status_code == 404


def test_kernel_status_reflects_lifecycle(
    client: TestClient, kernel_manager: KernelManager
) -> None:
    session_id = _upload(client)
    assert client.get(f"/sessions/{session_id}/kernel/status").json()["status"] == "stopped"
    client.post(f"/sessions/{session_id}/templates/overview/run")
    assert client.get(f"/sessions/{session_id}/kernel/status").json()["status"] == "running"


def test_export_produces_a_valid_zip(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/templates/overview/run")

    response = client.post(f"/sessions/{session_id}/notebook/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
        assert "data.ipynb" in names
        assert "requirements.txt" in names
        assert "data/README.md" in names
        assert "data/data.csv" not in names


def test_export_with_include_data_bundles_the_dataset(client: TestClient) -> None:
    session_id = _upload(client)
    client.post(f"/sessions/{session_id}/templates/overview/run")

    response = client.post(f"/sessions/{session_id}/notebook/export", params={"include_data": True})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "data/data.csv" in zf.namelist()
