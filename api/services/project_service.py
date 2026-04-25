"""Service layer for linking customer GCP projects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ulid import ULID

from agentcys_platform.models.project import CustomerProject
from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter

_CREDENTIALS_COLLECTION = "customer_credentials"
_PROJECTS_COLLECTION = "customer_projects"


class ProjectService:
    """Handles customer project verification and persistence."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def link_project(
        self,
        *,
        tenant_id: str,
        gcp_project_id: str,
        credential_id: str,
        default_region: str,
        state_bucket: str,
    ) -> CustomerProject:
        credential = await self._db.collection(_CREDENTIALS_COLLECTION).document(credential_id).get()
        if not credential.exists:
            raise ValueError("credential_not_found")

        credential_doc = credential.to_dict()
        if str(credential_doc.get("tenant_id")) != tenant_id:
            raise PermissionError("credential_tenant_mismatch")

        storage_client = self._build_storage_client(gcp_project_id)
        self._ensure_state_bucket(
            storage_client=storage_client,
            bucket_name=state_bucket,
            region=default_region,
        )

        project = CustomerProject(
            project_id=str(ULID()).lower(),
            gcp_project_id=gcp_project_id,
            tenant_id=tenant_id,
            default_region=default_region,
            credential_id=credential_id,
            state_bucket=state_bucket,
            created_at=datetime.now(UTC),
            status="linked",
        )

        await self._db.collection(_PROJECTS_COLLECTION).document(project.project_id).set(project.to_firestore())

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.PROJECT_LINKED,
                tenant_id=tenant_id,
                actor={"type": "api_key"},
                resource={"kind": "project", "id": project.project_id},
                outcome={"success": True},
                details={"gcp_project_id": gcp_project_id, "state_bucket": state_bucket},
            )
        )

        return project

    def _build_storage_client(self, gcp_project_id: str) -> Any:
        try:
            from google.cloud import storage  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("storage_client_unavailable") from exc

        return storage.Client(project=gcp_project_id)

    def _ensure_state_bucket(self, *, storage_client: Any, bucket_name: str, region: str) -> None:
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():
            bucket = storage_client.create_bucket(bucket_name, location=region)

        if not bool(getattr(bucket, "versioning_enabled", False)):
            bucket.versioning_enabled = True
            bucket.patch()
