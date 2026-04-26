"""Mirror Terraform state from the customer's state bucket into the platform mirror bucket."""

from __future__ import annotations

import logging
from typing import Any

from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter

logger = logging.getLogger(__name__)


def mirror_state(
    state_bucket: str,
    deployment_id: str,
    tenant_id: str,
    project_id: str,
    mirror_bucket: str,
    gcs_client: Any,
) -> None:
    """Copy the Terraform state file to the platform mirror bucket.

    Source:      ``gs://{state_bucket}/terraform/state/{deployment_id}/default.tfstate``
    Destination: ``gs://{mirror_bucket}/tenants/{tenant_id}/projects/{project_id}/
                  deployments/{deployment_id}/default.tfstate``

    Emits a STATE_MIRRORED audit event on success.
    Catches all exceptions, logs a warning, and does NOT re-raise so that a
    mirroring failure never rolls back an otherwise-successful deployment.
    """
    src_path = f"terraform/state/{deployment_id}/default.tfstate"
    dst_path = (
        f"tenants/{tenant_id}/projects/{project_id}/" f"deployments/{deployment_id}/default.tfstate"
    )

    try:
        src_bucket = gcs_client.bucket(state_bucket)
        src_blob = src_bucket.blob(src_path)

        # Download then re-upload (works across different bucket owners)
        state_bytes: bytes = src_blob.download_as_bytes()

        dst_bucket_obj = gcs_client.bucket(mirror_bucket)
        dst_blob = dst_bucket_obj.blob(dst_path)
        dst_blob.upload_from_string(state_bytes, content_type="application/json")

        logger.info(
            "Mirrored state: gs://%s/%s -> gs://%s/%s",
            state_bucket,
            src_path,
            mirror_bucket,
            dst_path,
        )

        # Schedule the audit event; mirror_state is sync but may be called
        # from within a running async context (execute_run).
        import asyncio

        event = AuditEvent(
            event_type=PlatformEvent.STATE_MIRRORED,
            tenant_id=tenant_id,
            actor={"type": "worker"},
            resource={"kind": "deployment", "id": deployment_id},
            details={
                "src": f"gs://{state_bucket}/{src_path}",
                "dst": f"gs://{mirror_bucket}/{dst_path}",
            },
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(audit_event_emitter.emit(event))
        except RuntimeError:
            # No running loop — safe to call run_until_complete
            asyncio.run(audit_event_emitter.emit(event))

    except Exception:
        logger.warning(
            "State mirroring failed for deployment %s — non-fatal, continuing",
            deployment_id,
            exc_info=True,
        )
