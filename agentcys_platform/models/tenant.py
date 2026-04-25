"""Tenant model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Tenant(BaseModel):
    model_config = ConfigDict()

    tenant_id: str
    name: str
    created_at: datetime
    plan: Literal["free", "pro", "enterprise"] = "free"

    def to_firestore(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "plan": self.plan,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> Tenant:
        created_at = doc["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            tenant_id=doc["tenant_id"],
            name=doc["name"],
            created_at=created_at,
            plan=doc.get("plan", "free"),
        )
