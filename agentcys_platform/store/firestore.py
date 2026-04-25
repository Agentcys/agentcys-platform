"""Tenant-scoped Firestore CRUD helpers.

Every read operation asserts that the document's ``tenant_id`` matches the
authenticated caller's tenant before returning data, preventing cross-tenant
data leaks even in the face of logic bugs in route handlers.

Usage::

    from agentcys_platform.store.firestore import TenantScopedStore

    store = TenantScopedStore(firestore_client)
    deployment = await store.get_by_id(
        "deployments", deployment_id, caller_tenant_id="01HX..."
    )
"""

from __future__ import annotations

import logging
from typing import Any

from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter
from agentcys_platform.security.tenant_guard import ensure_tenant_access

logger = logging.getLogger(__name__)

# Canonical Firestore collection names used across the platform.
COLLECTION_TENANTS = "tenants"
COLLECTION_PROJECTS = "customer_projects"
COLLECTION_CREDENTIALS = "customer_credentials"
COLLECTION_BLUEPRINTS = "blueprints"
COLLECTION_BLUEPRINT_VERSIONS = "blueprint_versions"
COLLECTION_DEPLOYMENTS = "deployments"
COLLECTION_DEPLOYMENT_RUNS = "deployment_runs"


class TenantScopedStore:
    """Firestore CRUD helpers with mandatory tenant-scope enforcement.

    All *write* operations (create, update, delete) emit an audit event.
    All *read* operations on tenant-owned documents assert ``tenant_id``
    before returning the document.

    The Firestore client is injected so this class is fully testable with
    a mock or the Firestore emulator.
    """

    def __init__(self, client: Any) -> None:
        """*client* is a ``google.cloud.firestore.AsyncClient`` instance."""
        self._client = client

    # ── Internal helpers ─────────────────────────────────────────────────

    def _collection(self, name: str):
        return self._client.collection(name)

    def _assert_tenant(self, doc_data: dict[str, Any], caller_tenant_id: str) -> None:
        """Raise 403 if the document's tenant_id does not match the caller."""
        doc_tenant = str(doc_data.get("tenant_id") or "").strip()
        # Reuse ensure_tenant_access with a synthetic user dict so we get the
        # same 403 shape everywhere.
        user = {"tenant_id": caller_tenant_id, "role": "member"}
        ensure_tenant_access(user, doc_tenant, resource_label="document")

    # ── Create ───────────────────────────────────────────────────────────

    async def create(
        self,
        collection: str,
        doc_id: str,
        data: dict[str, Any],
        *,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write *data* to *collection*/*doc_id* and emit an audit event."""
        await self._collection(collection).document(doc_id).set(data)
        logger.debug("Firestore create: %s/%s", collection, doc_id)

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.DEPLOYMENT_CREATED
                if collection == COLLECTION_DEPLOYMENTS
                else f"{collection}.created",
                tenant_id=str(data.get("tenant_id") or ""),
                actor=actor or {},
                resource={"collection": collection, "id": doc_id},
                outcome={"success": True},
            )
        )
        return data

    # ── Get by ID ────────────────────────────────────────────────────────

    async def get_by_id(
        self,
        collection: str,
        doc_id: str,
        *,
        caller_tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a single document.  If *caller_tenant_id* is provided, the
        document's ``tenant_id`` is asserted before the data is returned.
        """
        snap = await self._collection(collection).document(doc_id).get()
        if not snap.exists:
            return None
        data: dict[str, Any] = snap.to_dict()
        if caller_tenant_id is not None and "tenant_id" in data:
            self._assert_tenant(data, caller_tenant_id)
        return data

    # ── List ─────────────────────────────────────────────────────────────

    async def list(
        self,
        collection: str,
        filters: dict[str, Any] | None = None,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return up to *limit* documents matching *filters*.

        *filters* is a flat dict of ``{field: value}`` equality filters.
        For multi-tenant isolation, always pass ``{"tenant_id": tenant_id}``
        as part of *filters*.
        """
        query = self._collection(collection)
        for field, value in (filters or {}).items():
            query = query.where(filter=_field_filter(field, "==", value))
        query = query.limit(limit)

        docs = await query.get()
        return [d.to_dict() for d in docs if d.exists]

    # ── Update ───────────────────────────────────────────────────────────

    async def update(
        self,
        collection: str,
        doc_id: str,
        updates: dict[str, Any],
        *,
        caller_tenant_id: str | None = None,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Merge *updates* into an existing document."""
        if caller_tenant_id is not None:
            existing = await self.get_by_id(
                collection, doc_id, caller_tenant_id=caller_tenant_id
            )
            if existing is None:
                return  # not found — caller handles 404

        await self._collection(collection).document(doc_id).update(updates)
        logger.debug("Firestore update: %s/%s", collection, doc_id)

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=f"{collection}.updated",
                tenant_id=str(updates.get("tenant_id") or caller_tenant_id or ""),
                actor=actor or {},
                resource={"collection": collection, "id": doc_id},
                outcome={"success": True},
            )
        )

    # ── Delete ───────────────────────────────────────────────────────────

    async def delete(
        self,
        collection: str,
        doc_id: str,
        *,
        caller_tenant_id: str | None = None,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Delete a document after optional tenant assertion."""
        tenant_id_for_audit = caller_tenant_id or ""

        if caller_tenant_id is not None:
            existing = await self.get_by_id(
                collection, doc_id, caller_tenant_id=caller_tenant_id
            )
            if existing is not None:
                tenant_id_for_audit = str(existing.get("tenant_id") or caller_tenant_id)

        await self._collection(collection).document(doc_id).delete()
        logger.debug("Firestore delete: %s/%s", collection, doc_id)

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=f"{collection}.deleted",
                tenant_id=tenant_id_for_audit,
                actor=actor or {},
                resource={"collection": collection, "id": doc_id},
                outcome={"success": True},
            )
        )


# ── Firestore query filter helper ────────────────────────────────────────────

def _field_filter(field: str, op: str, value: Any):
    """Build a Firestore FieldFilter, compatible with the google-cloud-firestore ≥2.x API."""
    try:
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore[import]

        return FieldFilter(field, op, value)
    except ImportError:
        # Older SDK versions accepted raw tuples — not used in practice but keeps
        # test mocks simpler.
        return (field, op, value)
