"""Service layer for tenant and API key management."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from ulid import ULID

from agentcys_platform.models.tenant import Tenant

_TENANTS_COLLECTION = "tenants"
_TENANT_KEYS_COLLECTION = "tenant_api_keys"


class TenantService:
    """Creates tenants and issues tenant-scoped API keys."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def create_tenant(self, *, name: str, plan: str) -> Tenant:
        tenant = Tenant(
            tenant_id=str(ULID()).lower(),
            name=name.strip(),
            plan=plan,  # type: ignore[arg-type]
            created_at=datetime.now(UTC),
        )

        await self._db.collection(_TENANTS_COLLECTION).document(tenant.tenant_id).set(tenant.to_firestore())
        return tenant

    async def create_api_key(self, *, tenant_id: str, label: str | None = None) -> dict[str, str]:
        tenant_snap = await self._db.collection(_TENANTS_COLLECTION).document(tenant_id).get()
        if not tenant_snap.exists:
            raise ValueError("tenant_not_found")

        plaintext_key = f"ak_{secrets.token_urlsafe(36)}"
        key_hash = hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()
        key_id = str(ULID()).lower()
        created_at = datetime.now(UTC).isoformat()

        doc = {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "key_hash": key_hash,
            "label": (label or "").strip(),
            "created_at": created_at,
            "revoked_at": None,
        }

        await self._db.collection(_TENANT_KEYS_COLLECTION).document(key_id).set(doc)

        return {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "api_key": plaintext_key,
            "created_at": created_at,
        }
