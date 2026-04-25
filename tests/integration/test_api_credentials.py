"""Integration tests for POST /v1/credentials."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from api.main import create_app
from api.services.credential_service import CredentialService


class _DocSnapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data else {}


class _DocRef:
    def __init__(self, docs, doc_id):
        self._docs = docs
        self._id = doc_id

    async def set(self, data):
        self._docs[self._id] = dict(data)

    async def get(self):
        return _DocSnapshot(self._docs.get(self._id))


class _Query:
    def __init__(self, docs):
        self._filtered = list(docs.values())

    def where(self, *, filter=None, **_):
        if isinstance(filter, tuple):
            field, op, value = filter
            if op == "==":
                self._filtered = [d for d in self._filtered if d.get(field) == value]
        return self

    def limit(self, n):
        self._filtered = self._filtered[:n]
        return self

    async def get(self):
        return [_DocSnapshot(d) for d in self._filtered]


class _Collection:
    def __init__(self):
        self.docs = {}

    def document(self, doc_id):
        return _DocRef(self.docs, doc_id)

    def where(self, *, filter=None, **kwargs):
        return _Query(self.docs).where(filter=filter, **kwargs)


class _FakeDB:
    def __init__(self):
        self._collections = {
            "tenant_api_keys": _Collection(),
            "customer_credentials": _Collection(),
        }

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = _Collection()
        return self._collections[name]


def _valid_sa_key():
    return {
        "type": "service_account",
        "project_id": "demo-project",
        "private_key_id": "abc",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nX\\n-----END PRIVATE KEY-----\\n",
        "client_email": "svc@demo.iam.gserviceaccount.com",
        "client_id": "123",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def test_create_credential_201_and_no_secret_material(monkeypatch):
    db = _FakeDB()
    plaintext_key = "ak_test_credential"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    class _FakeCRM:
        def get_project(self, *, name):
            return {"name": name}

    class _FakeSM:
        def create_secret(self, request):
            return request

        def add_secret_version(self, request):
            class _Version:
                name = "projects/test/secrets/s1/versions/1"

            return _Version()

    monkeypatch.setattr(CredentialService, "_build_resource_manager_client", lambda self: _FakeCRM())
    monkeypatch.setattr(CredentialService, "_build_secret_manager_client", lambda self: _FakeSM())

    app = create_app()

    with TestClient(app) as client:
        client.app.state.db = db
        response = client.post(
            "/v1/credentials",
            headers={"X-API-Key": plaintext_key},
            json={"sa_key": _valid_sa_key()},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "tenant-1"
    assert "secret_manager_uri" not in body


def test_create_credential_invalid_payload_422(monkeypatch):
    db = _FakeDB()
    plaintext_key = "ak_test_credential"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    app = create_app()

    with TestClient(app) as client:
        client.app.state.db = db
        response = client.post(
            "/v1/credentials",
            headers={"X-API-Key": plaintext_key},
            json={"sa_key": {"type": "service_account"}},
        )

    assert response.status_code == 422
