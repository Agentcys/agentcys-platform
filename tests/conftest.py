"""Shared pytest fixtures for unit and integration tests.

Provides:
- two_tenants: a pair of tenant dicts for isolation tests
- mock_firestore: an in-memory Firestore-like client for unit tests
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Two-tenant fixture ───────────────────────────────────────────────────────

@pytest.fixture()
def tenant_alpha() -> dict[str, Any]:
    return {"tenant_id": "tenant-alpha-01", "role": "member"}


@pytest.fixture()
def tenant_beta() -> dict[str, Any]:
    return {"tenant_id": "tenant-beta-02", "role": "member"}


@pytest.fixture()
def platform_admin() -> dict[str, Any]:
    return {"tenant_id": "", "role": "platform_admin"}


# ── In-memory Firestore mock ─────────────────────────────────────────────────

class _FakeDocSnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data) if self._data else {}


class _FakeQuery:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = list(docs)

    def where(self, **_: Any) -> "_FakeQuery":  # noqa: ANN001
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._docs = self._docs[:n]
        return self

    async def get(self) -> list[_FakeDocSnapshot]:
        return [_FakeDocSnapshot(d) for d in self._docs]


class _FakeDocRef:
    def __init__(self, store: dict[str, Any], doc_id: str) -> None:
        self._store = store
        self._id = doc_id

    async def set(self, data: dict[str, Any]) -> None:
        self._store[self._id] = dict(data)

    async def get(self) -> _FakeDocSnapshot:
        return _FakeDocSnapshot(self._store.get(self._id))

    async def update(self, updates: dict[str, Any]) -> None:
        if self._id in self._store:
            self._store[self._id].update(updates)

    async def delete(self) -> None:
        self._store.pop(self._id, None)


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._docs, doc_id)

    def where(self, *, filter: Any = None, **_: Any) -> _FakeQuery:  # noqa: A002
        return _FakeQuery(list(self._docs.values()))

    def limit(self, n: int) -> _FakeQuery:
        return _FakeQuery(list(self._docs.values())[:n])

    async def get(self) -> list[_FakeDocSnapshot]:
        return [_FakeDocSnapshot(d) for d in self._docs.values()]


class FakeFirestoreClient:
    """Synchronous in-memory Firestore stand-in for unit tests."""

    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollection] = defaultdict(_FakeCollection)

    def collection(self, name: str) -> _FakeCollection:
        return self._collections[name]


@pytest.fixture()
def fake_firestore() -> FakeFirestoreClient:
    return FakeFirestoreClient()
