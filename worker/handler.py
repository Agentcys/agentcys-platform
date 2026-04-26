"""Cloud Tasks worker handler — full run orchestration."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from agentcys_platform.models.blueprint import BlueprintVersion
from agentcys_platform.models.credential import CustomerCredential
from agentcys_platform.models.deployment import Deployment
from agentcys_platform.models.project import CustomerProject
from agentcys_platform.models.run import DeploymentRun
from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter
from agentcys_platform.store.firestore import (
    COLLECTION_BLUEPRINT_VERSIONS,
    COLLECTION_CREDENTIALS,
    COLLECTION_DEPLOYMENT_RUNS,
    COLLECTION_DEPLOYMENTS,
    COLLECTION_PROJECTS,
)
from worker.config import get_worker_settings
from worker.terraform.runner import TerraformRunner
from worker.terraform.state_mirror import mirror_state
from worker.terraform.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _get_doc(firestore_client: Any, collection: str, doc_id: str) -> dict[str, Any]:
    snap = await firestore_client.collection(collection).document(doc_id).get()
    if not snap.exists:
        msg = f"Document {collection}/{doc_id} not found"
        raise ValueError(msg)
    return snap.to_dict()


async def _update_doc(
    firestore_client: Any, collection: str, doc_id: str, updates: dict[str, Any]
) -> None:
    await firestore_client.collection(collection).document(doc_id).update(updates)


async def _mark_run_failed(
    firestore_client: Any,
    run_id: str,
    error: str,
) -> None:
    await _update_doc(
        firestore_client,
        COLLECTION_DEPLOYMENT_RUNS,
        run_id,
        {"status": "failed", "error": error, "finished_at": _now()},
    )


async def _mark_deployment_failed(
    firestore_client: Any,
    deployment_id: str,
) -> None:
    await _update_doc(
        firestore_client,
        COLLECTION_DEPLOYMENTS,
        deployment_id,
        {"status": "failed", "updated_at": _now()},
    )


async def execute_run(
    run_id: str,
    deployment_id: str,
    firestore_client: Any,
    gcs_client: Any,
    secrets_client: Any,
) -> None:
    """Orchestrate a Terraform deployment run end-to-end.

    Steps:
        1. Load run; exit early if not queued (idempotency).
        2. Mark planning, load related documents.
        3. Fetch SA key from Secret Manager.
        4. Prepare workspace.
        5. Init / Plan / Apply or Destroy.
        6. Mirror Terraform state.
        7. Mark run succeeded.
    """
    settings = get_worker_settings()
    workspace: WorkspaceManager | None = None

    try:
        # 1. Load run; idempotency guard
        run_doc = await _get_doc(firestore_client, COLLECTION_DEPLOYMENT_RUNS, run_id)
        run = DeploymentRun.from_firestore(run_doc)
        if run.status != "queued":
            logger.info("Run %s is already %s — skipping", run_id, run.status)
            return

        # 2. Mark planning + load deployment
        await _update_doc(
            firestore_client,
            COLLECTION_DEPLOYMENT_RUNS,
            run_id,
            {"status": "planning", "started_at": _now()},
        )
        dep_doc = await _get_doc(firestore_client, COLLECTION_DEPLOYMENTS, deployment_id)
        deployment = Deployment.from_firestore(dep_doc)

        # 3. Load project, credential, blueprint version
        project_doc = await _get_doc(firestore_client, COLLECTION_PROJECTS, deployment.project_id)
        project = CustomerProject.from_firestore(project_doc)

        cred_doc = await _get_doc(firestore_client, COLLECTION_CREDENTIALS, project.credential_id)
        credential = CustomerCredential.from_firestore(cred_doc)

        bpv_doc = await _get_doc(
            firestore_client,
            COLLECTION_BLUEPRINT_VERSIONS,
            f"{deployment.blueprint_id}:{deployment.blueprint_version}",
        )
        blueprint_version = BlueprintVersion.from_firestore(bpv_doc)

        # 4. Fetch SA key from Secret Manager
        secret_response = secrets_client.access_secret_version(
            request={"name": credential.secret_manager_uri}
        )
        sa_key_bytes = secret_response.payload.data
        sa_key_data: dict[str, Any] = json.loads(sa_key_bytes)

        # Update credential last_used_at
        await _update_doc(
            firestore_client,
            COLLECTION_CREDENTIALS,
            credential.credential_id,
            {"last_used_at": _now()},
        )
        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.CREDENTIAL_ACCESSED,
                tenant_id=project.tenant_id,
                actor={"type": "worker", "run_id": run_id},
                resource={"kind": "credential", "id": credential.credential_id},
            )
        )

        # 5. Create workspace
        workspace = WorkspaceManager(run_id, settings.RUNS_BASE_DIR)
        workspace.create()
        sa_key_path = workspace.write_sa_key(sa_key_data)

        # 6. Download TF module from GCS
        module_dir = workspace.download_module(blueprint_version.tf_module_uri, gcs_client)

        # 7. Write terraform config files
        workspace.write_tfvars(
            deployment.params,
            {
                "project_id": project.gcp_project_id,
                "region": project.default_region,
                "resource_name_prefix": deployment.name,
            },
        )
        workspace.write_backend_tf(project.state_bucket, deployment_id)
        workspace.write_provider_tf(sa_key_path)

        # 8. Terraform init
        runner = TerraformRunner(
            working_dir=module_dir,
            sa_key_path=sa_key_path,
            tf_binary=settings.TF_BINARY,
        )
        init_result = runner.init(timeout=300)
        if init_result.returncode != 0:
            error = init_result.stderr.decode(errors="replace")
            logger.error("terraform init failed: %s", error)
            await _mark_run_failed(firestore_client, run_id, f"init failed: {error[:1000]}")
            await _mark_deployment_failed(firestore_client, deployment_id)
            await audit_event_emitter.emit(
                AuditEvent(
                    event_type=PlatformEvent.DEPLOYMENT_FAILED,
                    tenant_id=project.tenant_id,
                    actor={"type": "worker", "run_id": run_id},
                    resource={"kind": "deployment", "id": deployment_id},
                    details={"stage": "init"},
                )
            )
            workspace.cleanup()
            return

        # 9. Mark applying
        await _update_doc(
            firestore_client,
            COLLECTION_DEPLOYMENT_RUNS,
            run_id,
            {"status": "applying"},
        )

        # 10. Execute operation
        if run.operation == "apply":
            await audit_event_emitter.emit(
                AuditEvent(
                    event_type=PlatformEvent.DEPLOYMENT_STARTED,
                    tenant_id=project.tenant_id,
                    actor={"type": "worker", "run_id": run_id},
                    resource={"kind": "deployment", "id": deployment_id},
                )
            )

            plan_result = runner.plan(timeout=settings.TF_TIMEOUT_PLAN_SECONDS)
            if plan_result.returncode != 0:
                error = plan_result.stderr.decode(errors="replace")
                logger.error("terraform plan failed: %s", error)
                await _mark_run_failed(firestore_client, run_id, f"plan failed: {error[:1000]}")
                await _mark_deployment_failed(firestore_client, deployment_id)
                await audit_event_emitter.emit(
                    AuditEvent(
                        event_type=PlatformEvent.DEPLOYMENT_FAILED,
                        tenant_id=project.tenant_id,
                        actor={"type": "worker", "run_id": run_id},
                        resource={"kind": "deployment", "id": deployment_id},
                        details={"stage": "plan"},
                    )
                )
                workspace.cleanup()
                return

            apply_result = runner.apply(timeout=settings.TF_TIMEOUT_APPLY_SECONDS)
            if apply_result.returncode != 0:
                error = apply_result.stderr.decode(errors="replace")
                logger.error("terraform apply failed: %s", error)
                await _mark_run_failed(firestore_client, run_id, f"apply failed: {error[:1000]}")
                await _mark_deployment_failed(firestore_client, deployment_id)
                await audit_event_emitter.emit(
                    AuditEvent(
                        event_type=PlatformEvent.DEPLOYMENT_FAILED,
                        tenant_id=project.tenant_id,
                        actor={"type": "worker", "run_id": run_id},
                        resource={"kind": "deployment", "id": deployment_id},
                        details={"stage": "apply"},
                    )
                )
                workspace.cleanup()
                return

            outputs = runner.output_json()
            await _update_doc(
                firestore_client,
                COLLECTION_DEPLOYMENTS,
                deployment_id,
                {"outputs": outputs, "status": "applied", "updated_at": _now()},
            )
            await audit_event_emitter.emit(
                AuditEvent(
                    event_type=PlatformEvent.DEPLOYMENT_SUCCEEDED,
                    tenant_id=project.tenant_id,
                    actor={"type": "worker", "run_id": run_id},
                    resource={"kind": "deployment", "id": deployment_id},
                )
            )

        elif run.operation == "destroy":
            destroy_result = runner.destroy(timeout=settings.TF_TIMEOUT_DESTROY_SECONDS)
            if destroy_result.returncode != 0:
                error = destroy_result.stderr.decode(errors="replace")
                logger.error("terraform destroy failed: %s", error)
                await _mark_run_failed(firestore_client, run_id, f"destroy failed: {error[:1000]}")
                await _mark_deployment_failed(firestore_client, deployment_id)
                await audit_event_emitter.emit(
                    AuditEvent(
                        event_type=PlatformEvent.DEPLOYMENT_FAILED,
                        tenant_id=project.tenant_id,
                        actor={"type": "worker", "run_id": run_id},
                        resource={"kind": "deployment", "id": deployment_id},
                        details={"stage": "destroy"},
                    )
                )
                workspace.cleanup()
                return

            await _update_doc(
                firestore_client,
                COLLECTION_DEPLOYMENTS,
                deployment_id,
                {"outputs": None, "status": "destroyed", "updated_at": _now()},
            )
            await audit_event_emitter.emit(
                AuditEvent(
                    event_type=PlatformEvent.DEPLOYMENT_DESTROYED,
                    tenant_id=project.tenant_id,
                    actor={"type": "worker", "run_id": run_id},
                    resource={"kind": "deployment", "id": deployment_id},
                )
            )

        # 11. Mirror Terraform state
        mirror_state(
            state_bucket=project.state_bucket,
            deployment_id=deployment_id,
            tenant_id=project.tenant_id,
            project_id=project.project_id,
            mirror_bucket=settings.STATE_MIRROR_BUCKET,
            gcs_client=gcs_client,
        )

        # 12. Mark run succeeded
        await _update_doc(
            firestore_client,
            COLLECTION_DEPLOYMENT_RUNS,
            run_id,
            {"status": "succeeded", "finished_at": _now()},
        )

    except Exception:
        logger.exception("Unhandled error in execute_run for run_id=%s", run_id)
        try:
            await _mark_run_failed(firestore_client, run_id, "unexpected error")
            await _mark_deployment_failed(firestore_client, deployment_id)
            await audit_event_emitter.emit(
                AuditEvent(
                    event_type=PlatformEvent.DEPLOYMENT_FAILED,
                    actor={"type": "worker", "run_id": run_id},
                    resource={"kind": "deployment", "id": deployment_id},
                )
            )
        except Exception:
            logger.exception("Failed to record failure for run_id=%s", run_id)
    finally:
        if workspace is not None:
            workspace.cleanup()
