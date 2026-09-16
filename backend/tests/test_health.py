from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "llm" in body


def test_health_llm_mock_by_default() -> None:
    response = client.get("/health")
    body = response.json()
    assert body["llm"]["model"] == "mock"
    assert body["llm"]["configured"] is False
