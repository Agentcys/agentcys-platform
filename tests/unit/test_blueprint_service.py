"""Unit tests for blueprint service."""

from __future__ import annotations

import pytest

from api.services.blueprint_service import BlueprintService


class _DocSnapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data else {}


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

    def where(self, *, filter=None, **kwargs):
        return _Query(self.docs).where(filter=filter, **kwargs)

    def limit(self, n):
        return _Query(self.docs).limit(n)


class _FakeDB:
    def __init__(self):
        self._collections = {
            "blueprints": _Collection(),
            "blueprint_versions": _Collection(),
        }

    def collection(self, name):
        return self._collections[name]


@pytest.mark.asyncio
async def test_list_blueprints_includes_latest_version():
    db = _FakeDB()
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

    service = BlueprintService(db)
    items = await service.list_blueprints()

    assert len(items) == 1
    assert items[0]["latest"]["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_get_blueprint_with_latest_found():
    db = _FakeDB()
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

    service = BlueprintService(db)
    item = await service.get_blueprint_with_latest(blueprint_id="bp-1")

    assert item is not None
    assert item["blueprint_id"] == "bp-1"
    assert item["latest"]["tf_module_uri"].startswith("gs://")


@pytest.mark.asyncio
async def test_get_blueprint_with_latest_missing_returns_none():
    service = BlueprintService(_FakeDB())
    item = await service.get_blueprint_with_latest(blueprint_id="missing")
    assert item is None
