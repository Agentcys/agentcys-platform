"""Integration tests for POST /v1/projects."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from api.main import create_app
from api.services.project_service import ProjectService


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
            "customer_projects": _Collection(),
        }

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = _Collection()
        return self._collections[name]


def test_create_project_201(monkeypatch):
    db = _FakeDB()

    plaintext_key = "ak_test_projects"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    db.collection("customer_credentials").docs["cred-1"] = {
        "credential_id": "cred-1",
        "tenant_id": "tenant-1",
    }

    class _Bucket:
        def __init__(self):
            self.versioning_enabled = False

        def exists(self):
            return False

        def patch(self):
            return None

    class _Storage:
        def __init__(self):
            self._bucket = _Bucket()

        def bucket(self, _name):
            return self._bucket

        def create_bucket(self, _bucket_name, location):
            self.location = location
            return self._bucket

    monkeypatch.setattr(ProjectService, "_build_storage_client", lambda self, _pid: _Storage())

    app = create_app()

    with TestClient(app) as client:
        client.app.state.db = db
        response = client.post(
            "/v1/projects",
            headers={"X-API-Key": plaintext_key},
            json={
                "gcp_project_id": "customer-project",
                "credential_id": "cred-1",
                "default_region": "us-central1",
                "state_bucket": "customer-terraform-state",
            },
        )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == "tenant-1"


def test_create_project_404_missing_credential(monkeypatch):
    db = _FakeDB()

    plaintext_key = "ak_test_projects"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    monkeypatch.setattr(ProjectService, "_build_storage_client", lambda self, _pid: None)

    app = create_app()

    with TestClient(app) as client:
        client.app.state.db = db
        response = client.post(
            "/v1/projects",
            headers={"X-API-Key": plaintext_key},
            json={
                "gcp_project_id": "customer-project",
                "credential_id": "missing",
                "default_region": "us-central1",
                "state_bucket": "customer-terraform-state",
            },
        )

    assert response.status_code == 404
