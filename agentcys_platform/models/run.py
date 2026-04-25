"""DeploymentRun model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class DeploymentRun(BaseModel):
    model_config = ConfigDict()

    run_id: str
    deployment_id: str
    operation: Literal["apply", "destroy"]
    status: Literal["queued", "planning", "applying", "succeeded", "failed"] = "queued"
    tf_plan_uri: str | None = None
    tf_apply_log_uri: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    actor: dict[str, Any]

    def to_firestore(self) -> dict[str, Any]:
        def _iso(v: datetime | None) -> str | None:
            return v.isoformat() if v else None

        return {
            "run_id": self.run_id,
            "deployment_id": self.deployment_id,
            "operation": self.operation,
            "status": self.status,
            "tf_plan_uri": self.tf_plan_uri,
            "tf_apply_log_uri": self.tf_apply_log_uri,
            "error": self.error,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "actor": self.actor,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> "DeploymentRun":
        def _dt(v: str | None) -> datetime | None:
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        return cls(
            run_id=doc["run_id"],
            deployment_id=doc["deployment_id"],
            operation=doc["operation"],
            status=doc.get("status", "queued"),
            tf_plan_uri=doc.get("tf_plan_uri"),
            tf_apply_log_uri=doc.get("tf_apply_log_uri"),
            error=doc.get("error"),
            started_at=_dt(doc.get("started_at")),
            finished_at=_dt(doc.get("finished_at")),
            actor=doc.get("actor", {}),
        )
