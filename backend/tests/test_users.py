"""
Tests for workspace user management (Feature 1).
Validates Firestore user listing, activation, deactivation, token revocation,
self-deactivation prevention, last-admin protection, and audit logging.
"""

from fastapi.testclient import TestClient

from app.core.firebase_admin_client import set_mock_clients


class MockDocSnapshot:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data else {}


class MockDocRef:
    def __init__(self, doc_id: str, store: dict):
        self.id = doc_id
        self.store = store

    def get(self):
        data = self.store.get(self.id)
        return MockDocSnapshot(self.id, data)

    def update(self, fields: dict):
        if self.id in self.store:
            self.store[self.id].update(fields)


class MockCollectionRef:
    def __init__(self, store: dict):
        self.store = store

    def document(self, doc_id: str):
        return MockDocRef(doc_id, self.store)

    def stream(self):
        for doc_id, data in self.store.items():
            yield MockDocSnapshot(doc_id, data)


class MockFirestoreClient:
    def __init__(self, initial_users: dict):
        self.users_store = dict(initial_users)

    def collection(self, name: str):
        if name == "users":
            return MockCollectionRef(self.users_store)
        raise ValueError(f"Unknown mock collection {name}")


class MockAuthModule:
    def __init__(self):
        self.revoked_uids = []

    def revoke_refresh_tokens(self, uid: str):
        self.revoked_uids.append(uid)


def test_users_unconfigured_service_account(client: TestClient, auth_headers: dict):
    # Ensure unconfigured
    set_mock_clients(None, None)
    resp = client.get("/api/users", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert "not configured" in data["message"].lower()
    assert data["users"] == []


def test_users_list_and_filter(client: TestClient, auth_headers: dict):
    mock_store = {
        "uid_admin_1": {
            "name": "Jordan Davis",
            "email": "jordan.davis@acme.io",
            "role": "admin",
            "status": "active",
            "organizationId": "acme",
            "createdAt": "2026-10-01T10:00:00Z",
        },
        "uid_pending_1": {
            "name": "Taylor Swift",
            "email": "taylor.swift@acme.io",
            "role": "pending",
            "status": "pending",
            "organizationId": "acme",
            "createdAt": "2026-10-14T08:00:00Z",
        },
        "uid_other_org": {
            "name": "Eve Outsider",
            "email": "eve@evilcorp.io",
            "role": "admin",
            "status": "active",
            "organizationId": "other_corp",
            "createdAt": "2026-10-01T10:00:00Z",
        },
    }
    mock_fs = MockFirestoreClient(mock_store)
    mock_auth = MockAuthModule()
    set_mock_clients(mock_fs, mock_auth)

    try:
        # All acme users (other org excluded)
        resp = client.get("/api/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert len(data["users"]) == 2
        emails = [u["email"] for u in data["users"]]
        assert "eve@evilcorp.io" not in emails
        assert "taylor.swift@acme.io" in emails

        # Filter pending
        resp = client.get("/api/users?status=pending", headers=auth_headers)
        assert resp.status_code == 200
        pending_users = resp.json()["users"]
        assert len(pending_users) == 1
        assert pending_users[0]["email"] == "taylor.swift@acme.io"

        # Search query
        resp = client.get("/api/users?q=jordan", headers=auth_headers)
        assert resp.status_code == 200
        search_users = resp.json()["users"]
        assert len(search_users) == 1
        assert search_users[0]["name"] == "Jordan Davis"
    finally:
        set_mock_clients(None, None)


def test_user_activation_flow(client: TestClient, auth_headers: dict):
    mock_store = {
        "uid_pending_2": {
            "name": "Robin Hood",
            "email": "robin.hood@acme.io",
            "role": "pending",
            "status": "pending",
            "organizationId": "acme",
            "createdAt": "2026-10-14T09:00:00Z",
        }
    }
    mock_fs = MockFirestoreClient(mock_store)
    mock_auth = MockAuthModule()
    set_mock_clients(mock_fs, mock_auth)

    try:
        # Note is required (reject empty or missing)
        resp = client.post("/api/users/uid_pending_2/activate", headers=auth_headers, json={"note": ""})
        assert resp.status_code == 422

        # Valid activation
        resp = client.post(
            "/api/users/uid_pending_2/activate",
            headers=auth_headers,
            json={"note": "Verified by security lead for admin onboard"},
        )
        assert resp.status_code == 200
        assert resp.json()["newStatus"] == "active"
        assert resp.json()["role"] == "admin"

        # Verify in mock store
        assert mock_store["uid_pending_2"]["status"] == "active"
        assert mock_store["uid_pending_2"]["role"] == "admin"

        # Verify audit log event
        hist_resp = client.get("/api/history?action=User access", headers=auth_headers)
        assert hist_resp.status_code == 200
        events = hist_resp.json()["items"]
        assert any("User activated: Robin Hood" in e["title"] for e in events)
    finally:
        set_mock_clients(None, None)


def test_self_deactivation_forbidden(client: TestClient, auth_headers: dict):
    # In dev mode, user.uid is dev-admin-uid
    current_uid = "dev-admin-uid"
    mock_store = {
        current_uid: {
            "name": "Jordan Davis",
            "email": "jordan.davis@acme.io",
            "role": "admin",
            "status": "active",
            "organizationId": "acme",
        }
    }
    mock_fs = MockFirestoreClient(mock_store)
    mock_auth = MockAuthModule()
    set_mock_clients(mock_fs, mock_auth)

    try:
        resp = client.post(
            f"/api/users/{current_uid}/deactivate",
            headers=auth_headers,
            json={"note": "Attempt self deactivate"},
        )
        assert resp.status_code == 400
        assert "cannot deactivate their own account" in resp.json()["error"]["message"].lower()
    finally:
        set_mock_clients(None, None)


def test_last_active_admin_protection(client: TestClient, auth_headers: dict):
    # Only 1 active admin in acme
    solo_store = {
        "uid_solo": {
            "name": "Solo Admin",
            "email": "solo.admin@acme.io",
            "role": "admin",
            "status": "active",
            "organizationId": "acme",
        }
    }
    mock_fs = MockFirestoreClient(solo_store)
    mock_auth = MockAuthModule()
    set_mock_clients(mock_fs, mock_auth)

    try:
        resp = client.post(
            "/api/users/uid_solo/deactivate",
            headers=auth_headers,
            json={"note": "Attempt deactivate last admin"},
        )
        assert resp.status_code == 409
        assert "last active administrator" in resp.json()["error"]["message"].lower()
    finally:
        set_mock_clients(None, None)


def test_successful_deactivation_and_token_revocation(client: TestClient, auth_headers: dict):
    # 2 active admins in acme
    mock_store = {
        "dev-admin-uid": {
            "name": "Jordan Davis",
            "email": "jordan.davis@acme.io",
            "role": "admin",
            "status": "active",
            "organizationId": "acme",
        },
        "uid_admin_secondary": {
            "name": "Secondary Admin",
            "email": "secondary@acme.io",
            "role": "admin",
            "status": "active",
            "organizationId": "acme",
        },
    }
    mock_fs = MockFirestoreClient(mock_store)
    mock_auth = MockAuthModule()
    set_mock_clients(mock_fs, mock_auth)

    try:
        resp = client.post(
            "/api/users/uid_admin_secondary/deactivate",
            headers=auth_headers,
            json={"note": "Departing contractor privileges revoked"},
        )
        assert resp.status_code == 200
        assert resp.json()["newStatus"] == "disabled"
        assert mock_store["uid_admin_secondary"]["status"] == "disabled"
        # Verify Firebase refresh tokens were revoked
        assert "uid_admin_secondary" in mock_auth.revoked_uids

        # Verify audit log event
        hist_resp = client.get("/api/history?action=User access", headers=auth_headers)
        events = hist_resp.json()["items"]
        assert any("User deactivated: Secondary Admin" in e["title"] for e in events)
    finally:
        set_mock_clients(None, None)
