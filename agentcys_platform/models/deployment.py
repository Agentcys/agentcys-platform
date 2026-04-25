"""Deployment model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Deployment(BaseModel):
    model_config = ConfigDict()

    deployment_id: str
    tenant_id: str
    project_id: str
    blueprint_id: str
    blueprint_version: str
    name: str
    params: dict[str, Any]
    outputs: dict[str, Any] | None = None
    status: Literal["pending", "applying", "applied", "failed", "destroying", "destroyed"] = (
        "pending"
    )
    created_at: datetime
    updated_at: datetime
    current_run_id: str | None = None

    def to_firestore(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "blueprint_id": self.blueprint_id,
            "blueprint_version": self.blueprint_version,
            "name": self.name,
            "params": self.params,
            "outputs": self.outputs,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_run_id": self.current_run_id,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> Deployment:
        def _dt(v: str | datetime) -> datetime:
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        return cls(
            deployment_id=doc["deployment_id"],
            tenant_id=doc["tenant_id"],
            project_id=doc["project_id"],
            blueprint_id=doc["blueprint_id"],
            blueprint_version=doc["blueprint_version"],
            name=doc["name"],
            params=doc.get("params", {}),
            outputs=doc.get("outputs"),
            status=doc.get("status", "pending"),
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
            current_run_id=doc.get("current_run_id"),
        )
