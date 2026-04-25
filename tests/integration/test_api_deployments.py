"""Integration tests for deployment CRUD endpoints."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from api.main import create_app
from api.services.deployment_service import DeploymentService


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

    async def update(self, updates):
        if self._id in self._docs:
            self._docs[self._id].update(updates)


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
            "customer_projects": _Collection(),
            "blueprints": _Collection(),
            "blueprint_versions": _Collection(),
            "deployments": _Collection(),
            "deployment_runs": _Collection(),
        }

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = _Collection()
        return self._collections[name]


class _FakeTasksClient:
    def __init__(self):
        self.created = []

    def queue_path(self, project, location, queue):
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request):
        self.created.append(request)
        return {"name": "task-1"}


def _seed_auth_and_dependencies(db):
    plaintext_key = "ak_test_deployments"
    db.collection("tenant_api_keys").docs["key-1"] = {
        "key_id": "key-1",
        "tenant_id": "tenant-1",
        "key_hash": hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(),
        "revoked_at": None,
    }

    db.collection("customer_projects").docs["proj-1"] = {
        "project_id": "proj-1",
        "tenant_id": "tenant-1",
    }
    db.collection("blueprints").docs["bp-1"] = {
        "blueprint_id": "bp-1",
        "name": "Cloud Run",
        "description": "Deploy Cloud Run",
        "latest_version": "1.0.0",
    }
    db.collection("blueprint_versions").docs["bp-1-v1"] = {
        "blueprint_id": "bp-1",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "properties": {"service_name": {"type": "string"}},
            "required": ["service_name"],
        },
        "output_schema": {"type": "object"},
        "tf_module_uri": "gs://bucket/bp-1/1.0.0.tar.gz",
        "published_at": "2026-04-25T12:00:00+00:00",
        "immutable": True,
    }

    return plaintext_key


def test_deployment_create_list_get_delete(monkeypatch):
    db = _FakeDB()
    api_key = _seed_auth_and_dependencies(db)

    fake_tasks = _FakeTasksClient()
    monkeypatch.setattr(DeploymentService, "_build_tasks_client", lambda self: fake_tasks)

    app = create_app()
    with TestClient(app) as client:
        client.app.state.db = db

        created = client.post(
            "/v1/deployments",
            headers={"X-API-Key": api_key},
            json={
                "project_id": "proj-1",
                "blueprint_id": "bp-1",
                "name": "payments-api",
                "params": {"service_name": "payments"},
            },
        )
        assert created.status_code == 201
        deployment_id = created.json()["deployment"]["deployment_id"]

        listed = client.get("/v1/deployments", headers={"X-API-Key": api_key})
        assert listed.status_code == 200
        assert listed.json()["pagination"]["total"] >= 1

        fetched = client.get(f"/v1/deployments/{deployment_id}", headers={"X-API-Key": api_key})
        assert fetched.status_code == 200
        assert fetched.json()["deployment"]["name"] == "payments-api"

        # Mark deployment as applied to satisfy destroy precondition.
        db.collection("deployments").docs[deployment_id]["status"] = "applied"

        destroyed = client.delete(
            f"/v1/deployments/{deployment_id}", headers={"X-API-Key": api_key}
        )
        assert destroyed.status_code == 202
        assert destroyed.json()["queued"] is True

    assert len(fake_tasks.created) >= 2


def test_create_deployment_invalid_params_returns_422(monkeypatch):
    db = _FakeDB()
    api_key = _seed_auth_and_dependencies(db)

    monkeypatch.setattr(DeploymentService, "_build_tasks_client", lambda self: _FakeTasksClient())

    app = create_app()
    with TestClient(app) as client:
        client.app.state.db = db
        response = client.post(
            "/v1/deployments",
            headers={"X-API-Key": api_key},
            json={
                "project_id": "proj-1",
                "blueprint_id": "bp-1",
                "name": "payments-api",
                "params": {},
            },
        )

    assert response.status_code == 422
