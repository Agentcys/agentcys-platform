"""Integration tests for API key auth middleware."""

from __future__ import annotations

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.auth import APIKeyAuthMiddleware


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

    async def get(self):
        return _DocSnapshot(self._docs.get(self._id))


class _Query:
    def __init__(self, docs):
        self._docs = docs
        self._filtered = list(docs.values())

    def where(self, *, filter=None, **_):
        if isinstance(filter, tuple):
            field, op, value = filter
            if op == "==":
                self._filtered = [d for d in self._filtered if d.get(field) == value]
        else:
            field = getattr(filter, "field_path", "")
            op = getattr(filter, "op_string", "")
            value = getattr(filter, "value", None)
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
        self._collections = {"tenant_api_keys": _Collection()}

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = _Collection()
        return self._collections[name]


def _make_app(db):
    app = FastAPI()
    app.state.db = db
    app.add_middleware(APIKeyAuthMiddleware)

    @app.post("/v1/tenants")
    async def public_tenant_create():
        return {"ok": True}

    @app.get("/v1/protected")
    async def protected():
        return {"ok": True}

    return app


@pytest.fixture
def db():
    return _FakeDB()


def test_missing_api_key_rejected(db):
    app = _make_app(db)
    with TestClient(app) as client:
        response = client.get("/v1/protected")
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "missing_api_key"


def test_invalid_api_key_rejected(db):
    app = _make_app(db)
    with TestClient(app) as client:
        response = client.get("/v1/protected", headers={"X-API-Key": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_api_key"


def test_valid_api_key_allows_access(db):
    plaintext = "ak_test_valid"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    app = _make_app(db)
    with TestClient(app) as client:
        response = client.get("/v1/protected", headers={"X-API-Key": plaintext})
    assert response.status_code == 200


def test_public_tenant_bootstrap_route_skips_auth(db):
    app = _make_app(db)
    with TestClient(app) as client:
        response = client.post("/v1/tenants")
    assert response.status_code == 200
