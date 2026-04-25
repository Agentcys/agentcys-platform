"""Unit tests for project service."""

from __future__ import annotations

import pytest

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


class _Collection:
    def __init__(self):
        self.docs = {}

    def document(self, doc_id):
        return _DocRef(self.docs, doc_id)


class _FakeDB:
    def __init__(self):
        self._collections = {
            "customer_credentials": _Collection(),
            "customer_projects": _Collection(),
        }

    def collection(self, name):
        return self._collections[name]


class _Bucket:
    def __init__(self, exists=False):
        self._exists = exists
        self.versioning_enabled = False
        self.patched = False

    def exists(self):
        return self._exists

    def patch(self):
        self.patched = True


class _StorageClient:
    def __init__(self):
        self._bucket = _Bucket(exists=False)

    def bucket(self, name):
        self.name = name
        return self._bucket

    def create_bucket(self, bucket_name, location):
        self.created = (bucket_name, location)
        self._bucket._exists = True
        return self._bucket


@pytest.mark.asyncio
async def test_link_project_success(monkeypatch):
    db = _FakeDB()
    db.collection("customer_credentials").docs["cred-1"] = {
        "credential_id": "cred-1",
        "tenant_id": "tenant-1",
    }

    service = ProjectService(db)
    fake_storage = _StorageClient()
    monkeypatch.setattr(service, "_build_storage_client", lambda _project: fake_storage)

    project = await service.link_project(
        tenant_id="tenant-1",
        gcp_project_id="proj-x",
        credential_id="cred-1",
        default_region="us-central1",
        state_bucket="tf-state-bucket",
    )

    assert project.project_id in db.collection("customer_projects").docs
    assert fake_storage.created == ("tf-state-bucket", "us-central1")
    assert fake_storage._bucket.versioning_enabled is True


@pytest.mark.asyncio
async def test_missing_credential_raises():
    db = _FakeDB()
    service = ProjectService(db)

    with pytest.raises(ValueError, match="credential_not_found"):
        await service.link_project(
            tenant_id="tenant-1",
            gcp_project_id="proj-x",
            credential_id="missing",
            default_region="us-central1",
            state_bucket="tf-state-bucket",
        )


@pytest.mark.asyncio
async def test_credential_tenant_mismatch_raises():
    db = _FakeDB()
    db.collection("customer_credentials").docs["cred-1"] = {
        "credential_id": "cred-1",
        "tenant_id": "other-tenant",
    }
    service = ProjectService(db)

    with pytest.raises(PermissionError, match="credential_tenant_mismatch"):
        await service.link_project(
            tenant_id="tenant-1",
            gcp_project_id="proj-x",
            credential_id="cred-1",
            default_region="us-central1",
            state_bucket="tf-state-bucket",
        )
