"""CustomerProject model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CustomerProject(BaseModel):
    model_config = ConfigDict()

    project_id: str
    gcp_project_id: str
    tenant_id: str
    default_region: str
    credential_id: str
    state_bucket: str
    created_at: datetime
    status: Literal["linked", "unreachable", "revoked"] = "linked"

    def to_firestore(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "gcp_project_id": self.gcp_project_id,
            "tenant_id": self.tenant_id,
            "default_region": self.default_region,
            "credential_id": self.credential_id,
            "state_bucket": self.state_bucket,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> "CustomerProject":
        created_at = doc["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            project_id=doc["project_id"],
            gcp_project_id=doc["gcp_project_id"],
            tenant_id=doc["tenant_id"],
            default_region=doc["default_region"],
            credential_id=doc["credential_id"],
            state_bucket=doc["state_bucket"],
            created_at=created_at,
            status=doc.get("status", "linked"),
        )
