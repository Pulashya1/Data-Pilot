import io

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from tests.conftest import FakeStorageBackend

SAMPLE_DF = pd.DataFrame(
    {
        "id": range(1, 6),
        "name": ["a", "b", "c", "d", "e"],
        "score": [1.5, 2.5, None, 4.5, 5.5],
    }
)


def _csv_bytes() -> bytes:
    return SAMPLE_DF.to_csv(index=False).encode()


def _excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def test_upload_csv_creates_ready_session(client: TestClient) -> None:
    response = client.post(
        "/sessions", files={"file": ("sales.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert body["file_type"] == "csv"
    assert body["row_count"] == 5
    assert body["column_count"] == 3
    assert body["profile"]["n_rows"] == 5
    assert body["profile"]["data_quality"]["overall"] > 0


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/sessions", files={"file": ("virus.exe", io.BytesIO(b"nope"), "application/octet-stream")}
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post("/sessions", files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")})
    assert response.status_code == 400


def test_upload_enforces_size_limit(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(max_upload_size_mb=0)
    try:
        response = client.post(
            "/sessions", files={"file": ("sales.csv", io.BytesIO(_csv_bytes()), "text/csv")}
        )
        assert response.status_code == 413
    finally:
        del app.dependency_overrides[get_settings]


def test_multi_sheet_excel_requires_selection_then_finalizes(client: TestClient) -> None:
    raw = _excel_bytes({"First": SAMPLE_DF, "Second": SAMPLE_DF.head(2)})
    upload = client.post(
        "/sessions",
        files={
            "file": (
                "workbook.xlsx",
                io.BytesIO(raw),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201
    body = upload.json()
    assert body["status"] == "needs_sheet_selection"
    assert body["sheet_names"] == ["First", "Second"]
    assert body["profile"] is None
    session_id = body["id"]

    bad = client.post(f"/sessions/{session_id}/sheet", json={"sheet_name": "Nope"})
    assert bad.status_code == 400

    finalized = client.post(f"/sessions/{session_id}/sheet", json={"sheet_name": "Second"})
    assert finalized.status_code == 200
    finalized_body = finalized.json()
    assert finalized_body["status"] == "ready"
    assert finalized_body["selected_sheet"] == "Second"
    assert finalized_body["row_count"] == 2


def test_list_and_get_session(client: TestClient) -> None:
    upload = client.post(
        "/sessions", files={"file": ("sales.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    )
    session_id = upload.json()["id"]

    listing = client.get("/sessions")
    assert listing.status_code == 200
    assert any(s["id"] == session_id for s in listing.json())

    detail = client.get(f"/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == session_id


def test_get_unknown_session_404(client: TestClient) -> None:
    assert client.get("/sessions/does-not-exist").status_code == 404


def test_preview_pagination(client: TestClient) -> None:
    upload = client.post(
        "/sessions", files={"file": ("sales.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    )
    session_id = upload.json()["id"]

    preview = client.get(f"/sessions/{session_id}/preview", params={"offset": 1, "limit": 2})
    assert preview.status_code == 200
    body = preview.json()
    assert body["total_available"] == 5
    assert len(body["rows"]) == 2
    assert body["rows"][0]["id"] == 2


def test_delete_session_removes_it_and_its_storage_object(
    client: TestClient, fake_storage: FakeStorageBackend
) -> None:
    upload = client.post(
        "/sessions", files={"file": ("sales.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    )
    session_id = upload.json()["id"]
    assert len(fake_storage.objects) == 1

    deleted = client.delete(f"/sessions/{session_id}")
    assert deleted.status_code == 204
    assert client.get(f"/sessions/{session_id}").status_code == 404
    assert len(fake_storage.objects) == 0
