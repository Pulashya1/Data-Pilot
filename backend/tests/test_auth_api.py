"""Auth API tests (MASTER_PROMPT.md §9, §12 Phase 8): the magic-link login flow, session-cookie
enforcement, and cross-user session isolation.

Uses `raw_client` (no `get_current_user` override) since the login flow itself is exactly
what's under test — every other test file uses the fixed `test_user` override from `client`
instead, since they only care about the *protected* behavior, not auth itself.
"""

import io

from fastapi.testclient import TestClient


def _upload(client: TestClient) -> str:
    response = client.post(
        "/sessions", files={"file": ("data.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}
    )
    assert response.status_code == 201
    return response.json()["id"]  # type: ignore[no-any-return]


def _login(client: TestClient, email: str) -> None:
    response = client.post("/auth/request-link", json={"email": email})
    assert response.status_code == 200
    login_url = response.json()["dev_login_url"]
    assert login_url is not None
    token = login_url.rsplit("token=", 1)[1]
    verify_response = client.get(f"/auth/verify?token={token}")
    assert verify_response.status_code == 200
    assert verify_response.json()["email"] == email


def test_protected_routes_require_auth(raw_client: TestClient) -> None:
    assert raw_client.get("/sessions").status_code == 401
    assert raw_client.get("/auth/me").status_code == 401


def test_request_link_dev_mode_returns_a_usable_link(raw_client: TestClient) -> None:
    response = raw_client.post("/auth/request-link", json={"email": "person@example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["dev_login_url"] is not None
    assert "token=" in body["dev_login_url"]


def test_request_link_rejects_a_malformed_email(raw_client: TestClient) -> None:
    response = raw_client.post("/auth/request-link", json={"email": "not-an-email"})
    assert response.status_code == 422


def test_full_login_flow_grants_access(raw_client: TestClient) -> None:
    _login(raw_client, "alice@example.com")
    me = raw_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"
    assert raw_client.get("/sessions").status_code == 200


def test_a_login_token_can_only_be_used_once(raw_client: TestClient) -> None:
    response = raw_client.post("/auth/request-link", json={"email": "bob@example.com"})
    token = response.json()["dev_login_url"].rsplit("token=", 1)[1]
    first = raw_client.get(f"/auth/verify?token={token}")
    assert first.status_code == 200
    second = raw_client.get(f"/auth/verify?token={token}")
    assert second.status_code == 400


def test_verify_rejects_an_unknown_token(raw_client: TestClient) -> None:
    response = raw_client.get("/auth/verify?token=not-a-real-token")
    assert response.status_code == 400


def test_logout_clears_the_session(raw_client: TestClient) -> None:
    _login(raw_client, "carol@example.com")
    assert raw_client.get("/auth/me").status_code == 200
    assert raw_client.post("/auth/logout").status_code == 200
    assert raw_client.get("/auth/me").status_code == 401


def test_users_cannot_see_each_others_sessions(raw_client: TestClient) -> None:
    _login(raw_client, "owner@example.com")
    session_id = _upload(raw_client)
    assert raw_client.get(f"/sessions/{session_id}").status_code == 200

    raw_client.post("/auth/logout")
    _login(raw_client, "intruder@example.com")
    assert raw_client.get(f"/sessions/{session_id}").status_code == 404
    assert session_id not in [s["id"] for s in raw_client.get("/sessions").json()]
