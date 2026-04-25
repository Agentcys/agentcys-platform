"""Unit tests for tenant service."""

from __future__ import annotations

import hashlib

import pytest

from api.services.tenant_service import TenantService


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
        self.collections = {
            "tenants": _Collection(),
            "tenant_api_keys": _Collection(),
        }

    def collection(self, name):
        return self.collections[name]


@pytest.mark.asyncio
async def test_create_tenant_persists_document():
    db = _FakeDB()
    service = TenantService(db)

    tenant = await service.create_tenant(name="Acme", plan="pro")

    assert tenant.tenant_id in db.collection("tenants").docs
    assert db.collection("tenants").docs[tenant.tenant_id]["plan"] == "pro"


@pytest.mark.asyncio
async def test_create_api_key_stores_hash_only():
    db = _FakeDB()
    service = TenantService(db)

    tenant = await service.create_tenant(name="Acme", plan="free")
    created = await service.create_api_key(tenant_id=tenant.tenant_id)

    stored = db.collection("tenant_api_keys").docs[created["key_id"]]
    assert stored["tenant_id"] == tenant.tenant_id
    assert stored["key_hash"] == hashlib.sha256(created["api_key"].encode("utf-8")).hexdigest()
    assert "api_key" not in stored


@pytest.mark.asyncio
async def test_create_api_key_for_unknown_tenant_raises():
    db = _FakeDB()
    service = TenantService(db)

    with pytest.raises(ValueError, match="tenant_not_found"):
        await service.create_api_key(tenant_id="missing")
