"""Unit tests for credential service."""

from __future__ import annotations

import pytest

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


class _Collection:
    def __init__(self):
        self.docs = {}

    def document(self, doc_id):
        return _DocRef(self.docs, doc_id)


class _FakeDB:
    def __init__(self):
        self._collections = {"customer_credentials": _Collection()}

    def collection(self, name):
        return self._collections[name]


class _FakeSettings:
    SECRET_MANAGER_PROJECT = "secrets-proj"  # noqa: S105


class _FakeCRMClient:
    def get_project(self, *, name):
        return {"name": name}


class _FakeSMClient:
    def create_secret(self, request):
        return request

    def add_secret_version(self, request):
        class _Version:
            name = "projects/secrets-proj/secrets/foo/versions/1"

        return _Version()


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


@pytest.mark.asyncio
async def test_create_credential_persists_metadata(monkeypatch):
    db = _FakeDB()
    service = CredentialService(db, _FakeSettings())

    monkeypatch.setattr(service, "_build_resource_manager_client", lambda: _FakeCRMClient())
    monkeypatch.setattr(service, "_build_secret_manager_client", lambda: _FakeSMClient())

    credential = await service.create_credential(tenant_id="tenant-1", sa_key=_valid_sa_key())

    assert credential.tenant_id == "tenant-1"
    assert credential.credential_id in db.collection("customer_credentials").docs


@pytest.mark.asyncio
async def test_missing_required_fields_raises():
    db = _FakeDB()
    service = CredentialService(db, _FakeSettings())

    with pytest.raises(ValueError, match="missing_sa_key_fields"):
        await service.create_credential(tenant_id="tenant-1", sa_key={"type": "service_account"})


@pytest.mark.asyncio
async def test_project_access_denied_raises(monkeypatch):
    db = _FakeDB()
    service = CredentialService(db, _FakeSettings())

    class _DeniedCRM:
        def get_project(self, *, name):
            raise RuntimeError(name)

    monkeypatch.setattr(service, "_build_resource_manager_client", lambda: _DeniedCRM())

    with pytest.raises(PermissionError, match="project_access_denied"):
        await service.create_credential(tenant_id="tenant-1", sa_key=_valid_sa_key())
