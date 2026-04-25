"""Unit tests for deployment service."""

from __future__ import annotations

import pytest

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
            "customer_projects": _Collection(),
            "blueprints": _Collection(),
            "blueprint_versions": _Collection(),
            "deployments": _Collection(),
            "deployment_runs": _Collection(),
        }

    def collection(self, name):
        return self._collections[name]


class _Settings:
    GCP_PROJECT_ID = "platform-proj"
    CLOUD_TASKS_LOCATION = "us-central1"
    CLOUD_TASKS_QUEUE = "deployments"
    DEPLOYMENT_TASK_TARGET_URL = "https://worker.invalid/tasks/deployments"


class _FakeTasksClient:
    def __init__(self):
        self.created = []

    def queue_path(self, project, location, queue):
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request):
        self.created.append(request)
        return {"name": "task-1"}


def _seed_dependencies(db):
    db.collection("customer_projects").docs["proj-1"] = {
        "project_id": "proj-1",
        "tenant_id": "tenant-1",
    }
    db.collection("blueprints").docs["bp-1"] = {
        "blueprint_id": "bp-1",
        "name": "Cloud Run",
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
    }


@pytest.mark.asyncio
async def test_create_deployment_enqueues_apply(monkeypatch):
    db = _FakeDB()
    _seed_dependencies(db)
    service = DeploymentService(db, _Settings())

    fake_tasks = _FakeTasksClient()
    monkeypatch.setattr(service, "_build_tasks_client", lambda: fake_tasks)

    deployment, run = await service.create_deployment(
        tenant_id="tenant-1",
        actor={"type": "api_key", "id": "key-1"},
        project_id="proj-1",
        blueprint_id="bp-1",
        blueprint_version=None,
        name="payments-api",
        params={"service_name": "payments"},
    )

    assert deployment.deployment_id in db.collection("deployments").docs
    assert run.run_id in db.collection("deployment_runs").docs
    assert len(fake_tasks.created) == 1


@pytest.mark.asyncio
async def test_create_deployment_duplicate_name_raises(monkeypatch):
    db = _FakeDB()
    _seed_dependencies(db)
    db.collection("deployments").docs["dep-existing"] = {
        "deployment_id": "dep-existing",
        "tenant_id": "tenant-1",
        "name": "payments-api",
        "status": "applied",
        "created_at": "2026-04-25T10:00:00+00:00",
    }

    service = DeploymentService(db, _Settings())
    monkeypatch.setattr(service, "_build_tasks_client", lambda: _FakeTasksClient())

    with pytest.raises(ValueError, match="deployment_name_already_exists"):
        await service.create_deployment(
            tenant_id="tenant-1",
            actor={"type": "api_key", "id": "key-1"},
            project_id="proj-1",
            blueprint_id="bp-1",
            blueprint_version=None,
            name="payments-api",
            params={"service_name": "payments"},
        )


@pytest.mark.asyncio
async def test_destroy_deployment_requires_applied(monkeypatch):
    db = _FakeDB()
    _seed_dependencies(db)
    db.collection("deployments").docs["dep-1"] = {
        "deployment_id": "dep-1",
        "tenant_id": "tenant-1",
        "status": "pending",
        "current_run_id": None,
    }

    service = DeploymentService(db, _Settings())
    monkeypatch.setattr(service, "_build_tasks_client", lambda: _FakeTasksClient())

    with pytest.raises(ValueError, match="deployment_not_applied"):
        await service.destroy_deployment(
            tenant_id="tenant-1",
            deployment_id="dep-1",
            actor={"type": "api_key", "id": "key-1"},
        )
