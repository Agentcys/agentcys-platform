"""Integration tests for blueprint catalog endpoints."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from api.main import create_app


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

    def limit(self, n):
        return _Query(self.docs).limit(n)


class _FakeDB:
    def __init__(self):
        self._collections = {
            "tenant_api_keys": _Collection(),
            "blueprints": _Collection(),
            "blueprint_versions": _Collection(),
        }

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = _Collection()
        return self._collections[name]


def _seed_blueprint_data(db):
    db.collection("blueprints").docs["bp-1"] = {
        "blueprint_id": "bp-1",
        "name": "Cloud Run",
        "description": "Deploy Cloud Run",
        "latest_version": "1.0.0",
    }
    db.collection("blueprint_versions").docs["bp-1-v1"] = {
        "blueprint_id": "bp-1",
        "version": "1.0.0",
        "tf_module_uri": "gs://bucket/bp-1/1.0.0.tar.gz",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "published_at": "2026-04-25T12:00:00+00:00",
        "immutable": True,
    }


def test_list_blueprints_authenticated():
    db = _FakeDB()
    _seed_blueprint_data(db)

    plaintext_key = "ak_test_blueprints"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    app = create_app()
    with TestClient(app) as client:
        client.app.state.db = db
        response = client.get("/v1/blueprints", headers={"X-API-Key": plaintext_key})

    assert response.status_code == 200
    assert response.json()["items"][0]["latest_version"] == "1.0.0"


def test_get_blueprint_not_found_returns_404():
    db = _FakeDB()

    plaintext_key = "ak_test_blueprints"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    app = create_app()
    with TestClient(app) as client:
        client.app.state.db = db
        response = client.get("/v1/blueprints/missing", headers={"X-API-Key": plaintext_key})

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "blueprint_not_found"
