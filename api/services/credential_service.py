"""Service layer for customer credential onboarding."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ulid import ULID

from agentcys_platform.models.credential import CustomerCredential
from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter

_CREDENTIALS_COLLECTION = "customer_credentials"
_REQUIRED_SA_KEY_FIELDS = {
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "token_uri",
}


class CredentialService:
    """Handles credential validation, project-access verification, and persistence."""

    def __init__(self, db: Any, settings: Any) -> None:
        self._db = db
        self._settings = settings

    async def create_credential(self, *, tenant_id: str, sa_key: dict[str, Any]) -> CustomerCredential:
        self._validate_sa_key(sa_key)

        project_id = str(sa_key["project_id"])
        crm_client = self._build_resource_manager_client()
        self._verify_project_access(crm_client, project_id)

        credential_id = str(ULID()).lower()
        secret_uri = self._store_secret(
            credential_id=credential_id,
            tenant_id=tenant_id,
            sa_key=sa_key,
        )

        credential = CustomerCredential(
            credential_id=credential_id,
            tenant_id=tenant_id,
            kind="sa_key",
            secret_manager_uri=secret_uri,
            sa_email=str(sa_key["client_email"]),
            created_at=datetime.now(UTC),
        )

        await self._db.collection(_CREDENTIALS_COLLECTION).document(credential_id).set(
            credential.to_firestore()
        )

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.CREDENTIAL_UPLOADED,
                tenant_id=tenant_id,
                actor={"type": "api_key"},
                resource={"kind": "credential", "id": credential_id},
                outcome={"success": True},
                details={"project_id": project_id, "sa_email": credential.sa_email},
            )
        )

        return credential

    def _validate_sa_key(self, sa_key: dict[str, Any]) -> None:
        missing = sorted(field for field in _REQUIRED_SA_KEY_FIELDS if not sa_key.get(field))
        if missing:
            raise ValueError(f"missing_sa_key_fields:{','.join(missing)}")

        if sa_key.get("type") != "service_account":
            raise ValueError("invalid_sa_key_type")

    def _build_resource_manager_client(self) -> Any:
        try:
            from google.cloud import resourcemanager_v3  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("resource_manager_client_unavailable") from exc

        return resourcemanager_v3.ProjectsClient()

    def _verify_project_access(self, crm_client: Any, project_id: str) -> None:
        try:
            crm_client.get_project(name=f"projects/{project_id}")
        except Exception as exc:  # noqa: BLE001
            raise PermissionError("project_access_denied") from exc

    def _build_secret_manager_client(self) -> Any:
        try:
            from google.cloud import secretmanager  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("secret_manager_client_unavailable") from exc

        return secretmanager.SecretManagerServiceClient()

    def _store_secret(self, *, credential_id: str, tenant_id: str, sa_key: dict[str, Any]) -> str:
        secret_client = self._build_secret_manager_client()
        parent = f"projects/{self._settings.SECRET_MANAGER_PROJECT}"
        secret_id = f"tenant-{tenant_id}-{credential_id}"

        secret_client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )

        version = secret_client.add_secret_version(
            request={
                "parent": f"{parent}/secrets/{secret_id}",
                "payload": {"data": json.dumps(sa_key).encode("utf-8")},
            }
        )
        return version.name
