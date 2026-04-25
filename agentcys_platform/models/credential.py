"""CustomerCredential model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CustomerCredential(BaseModel):
    model_config = ConfigDict()

    credential_id: str
    tenant_id: str
    kind: Literal["sa_key", "wif"] = "sa_key"
    secret_manager_uri: str
    sa_email: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def to_firestore(self) -> dict[str, Any]:
        return {
            "credential_id": self.credential_id,
            "tenant_id": self.tenant_id,
            "kind": self.kind,
            "secret_manager_uri": self.secret_manager_uri,
            "sa_email": self.sa_email,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> "CustomerCredential":
        def _dt(v: str | None) -> datetime | None:
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        created_at = doc["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            credential_id=doc["credential_id"],
            tenant_id=doc["tenant_id"],
            kind=doc.get("kind", "sa_key"),
            secret_manager_uri=doc["secret_manager_uri"],
            sa_email=doc["sa_email"],
            created_at=created_at,
            last_used_at=_dt(doc.get("last_used_at")),
            revoked_at=_dt(doc.get("revoked_at")),
        )
