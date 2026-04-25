"""Service layer for deployment lifecycle and queueing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ulid import ULID

from agentcys_platform.models.deployment import Deployment
from agentcys_platform.models.run import DeploymentRun
from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter

_BLUEPRINTS_COLLECTION = "blueprints"
_BLUEPRINT_VERSIONS_COLLECTION = "blueprint_versions"
_DEPLOYMENTS_COLLECTION = "deployments"
_DEPLOYMENT_RUNS_COLLECTION = "deployment_runs"
_PROJECTS_COLLECTION = "customer_projects"


class DeploymentService:
    """Handles deployment creation, listing, retrieval, and destroy queueing."""

    def __init__(self, db: Any, settings: Any) -> None:
        self._db = db
        self._settings = settings

    async def create_deployment(
        self,
        *,
        tenant_id: str,
        actor: dict[str, Any],
        project_id: str,
        blueprint_id: str,
        blueprint_version: str | None,
        name: str,
        params: dict[str, Any],
    ) -> tuple[Deployment, DeploymentRun]:
        project = await self._get_project(project_id)
        if project is None:
            raise ValueError("project_not_found")
        if str(project.get("tenant_id")) != tenant_id:
            raise PermissionError("project_tenant_mismatch")

        blueprint = await self._get_blueprint(blueprint_id)
        if blueprint is None:
            raise ValueError("blueprint_not_found")

        version = blueprint_version or str(blueprint.get("latest_version") or "")
        version_doc = await self._get_blueprint_version(blueprint_id=blueprint_id, version=version)
        if version_doc is None:
            raise ValueError("blueprint_version_not_found")

        if not _validate_params_against_schema(
            params=params, schema=version_doc.get("input_schema") or {}
        ):
            raise ValueError("params_schema_invalid")

        if await self._name_exists_for_tenant(tenant_id=tenant_id, name=name):
            raise ValueError("deployment_name_already_exists")

        now = datetime.now(UTC)
        deployment = Deployment(
            deployment_id=str(ULID()).lower(),
            tenant_id=tenant_id,
            project_id=project_id,
            blueprint_id=blueprint_id,
            blueprint_version=version,
            name=name,
            params=params,
            outputs=None,
            status="pending",
            created_at=now,
            updated_at=now,
            current_run_id=None,
        )

        run = DeploymentRun(
            run_id=str(ULID()).lower(),
            deployment_id=deployment.deployment_id,
            operation="apply",
            status="queued",
            actor=actor,
        )
        deployment.current_run_id = run.run_id

        await self._db.collection(_DEPLOYMENTS_COLLECTION).document(deployment.deployment_id).set(
            deployment.to_firestore()
        )
        await self._db.collection(_DEPLOYMENT_RUNS_COLLECTION).document(run.run_id).set(
            run.to_firestore()
        )

        self._enqueue_run(
            run_id=run.run_id, deployment_id=deployment.deployment_id, operation="apply"
        )

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.DEPLOYMENT_CREATED,
                tenant_id=tenant_id,
                actor=actor,
                resource={"kind": "deployment", "id": deployment.deployment_id},
                outcome={"success": True},
                details={"run_id": run.run_id},
            )
        )

        return deployment, run

    async def get_deployment(self, *, tenant_id: str, deployment_id: str) -> dict[str, Any] | None:
        dep = await self._db.collection(_DEPLOYMENTS_COLLECTION).document(deployment_id).get()
        if not dep.exists:
            return None

        deployment = dep.to_dict()
        if str(deployment.get("tenant_id")) != tenant_id:
            raise PermissionError("deployment_tenant_mismatch")

        run: dict[str, Any] | None = None
        run_id = deployment.get("current_run_id")
        if run_id:
            run_snap = (
                await self._db.collection(_DEPLOYMENT_RUNS_COLLECTION).document(str(run_id)).get()
            )
            if run_snap.exists:
                run = run_snap.to_dict()

        return {"deployment": deployment, "current_run": run}

    async def list_deployments(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        docs = (
            await self._db.collection(_DEPLOYMENTS_COLLECTION)
            .where(filter=("tenant_id", "==", tenant_id))
            .limit(500)
            .get()
        )

        items = [d.to_dict() for d in docs if d.exists]
        if project_id:
            items = [i for i in items if i.get("project_id") == project_id]
        if status:
            items = [i for i in items if i.get("status") == status]

        items.sort(key=lambda i: str(i.get("created_at", "")), reverse=True)
        total = len(items)
        page = items[offset : offset + limit]

        return {
            "items": page,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(page),
                "total": total,
            },
        }

    async def destroy_deployment(
        self,
        *,
        tenant_id: str,
        deployment_id: str,
        actor: dict[str, Any],
    ) -> tuple[dict[str, Any], DeploymentRun]:
        dep_snap = await self._db.collection(_DEPLOYMENTS_COLLECTION).document(deployment_id).get()
        if not dep_snap.exists:
            raise ValueError("deployment_not_found")

        deployment = dep_snap.to_dict()
        if str(deployment.get("tenant_id")) != tenant_id:
            raise PermissionError("deployment_tenant_mismatch")

        if str(deployment.get("status")) != "applied":
            raise ValueError("deployment_not_applied")

        run = DeploymentRun(
            run_id=str(ULID()).lower(),
            deployment_id=deployment_id,
            operation="destroy",
            status="queued",
            actor=actor,
        )
        await self._db.collection(_DEPLOYMENT_RUNS_COLLECTION).document(run.run_id).set(
            run.to_firestore()
        )

        updated = {
            "status": "destroying",
            "updated_at": datetime.now(UTC).isoformat(),
            "current_run_id": run.run_id,
        }
        await self._db.collection(_DEPLOYMENTS_COLLECTION).document(deployment_id).update(updated)
        deployment.update(updated)

        self._enqueue_run(run_id=run.run_id, deployment_id=deployment_id, operation="destroy")

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.DEPLOYMENT_DESTROYED,
                tenant_id=tenant_id,
                actor=actor,
                resource={"kind": "deployment", "id": deployment_id},
                outcome={"success": True},
                reason="queued",
                details={"run_id": run.run_id, "operation": "destroy"},
            )
        )

        return deployment, run

    async def _name_exists_for_tenant(self, *, tenant_id: str, name: str) -> bool:
        docs = (
            await self._db.collection(_DEPLOYMENTS_COLLECTION)
            .where(filter=("tenant_id", "==", tenant_id))
            .where(filter=("name", "==", name))
            .limit(5)
            .get()
        )
        for snap in docs:
            if not snap.exists:
                continue
            if str(snap.to_dict().get("status")) != "destroyed":
                return True
        return False

    async def _get_project(self, project_id: str) -> dict[str, Any] | None:
        snap = await self._db.collection(_PROJECTS_COLLECTION).document(project_id).get()
        if not snap.exists:
            return None
        return snap.to_dict()

    async def _get_blueprint(self, blueprint_id: str) -> dict[str, Any] | None:
        docs = (
            await self._db.collection(_BLUEPRINTS_COLLECTION)
            .where(filter=("blueprint_id", "==", blueprint_id))
            .limit(1)
            .get()
        )
        if not docs:
            return None
        snap = docs[0]
        if not snap.exists:
            return None
        return snap.to_dict()

    async def _get_blueprint_version(
        self, *, blueprint_id: str, version: str
    ) -> dict[str, Any] | None:
        docs = (
            await self._db.collection(_BLUEPRINT_VERSIONS_COLLECTION)
            .where(filter=("blueprint_id", "==", blueprint_id))
            .where(filter=("version", "==", version))
            .limit(1)
            .get()
        )
        if not docs:
            return None
        snap = docs[0]
        if not snap.exists:
            return None
        return snap.to_dict()

    def _build_tasks_client(self) -> Any:
        try:
            from google.cloud import tasks_v2  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("cloud_tasks_client_unavailable") from exc
        return tasks_v2.CloudTasksClient()

    def _enqueue_run(self, *, run_id: str, deployment_id: str, operation: str) -> None:
        tasks_client = self._build_tasks_client()
        parent = tasks_client.queue_path(
            self._settings.GCP_PROJECT_ID,
            self._settings.CLOUD_TASKS_LOCATION,
            self._settings.CLOUD_TASKS_QUEUE,
        )

        payload = {
            "run_id": run_id,
            "deployment_id": deployment_id,
            "operation": operation,
        }

        task = {
            "http_request": {
                "http_method": 1,
                "url": self._settings.DEPLOYMENT_TASK_TARGET_URL,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode("utf-8"),
            }
        }
        tasks_client.create_task(request={"parent": parent, "task": task})


def _validate_params_against_schema(*, params: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Validate params against a strict subset of JSON Schema used by blueprint inputs."""
    schema_type = schema.get("type")
    if schema_type and schema_type != "object":
        return False

    if not isinstance(params, dict):
        return False

    required = schema.get("required") or []
    if any(key not in params for key in required):
        return False

    properties = schema.get("properties") or {}
    for key, definition in properties.items():
        if key not in params:
            continue
        expected_type = str((definition or {}).get("type") or "")
        if expected_type == "string" and not isinstance(params[key], str):
            return False
        if expected_type == "number" and not isinstance(params[key], (int, float)):
            return False
        if expected_type == "integer" and not isinstance(params[key], int):
            return False
        if expected_type == "boolean" and not isinstance(params[key], bool):
            return False
        if expected_type == "object" and not isinstance(params[key], dict):
            return False
        if expected_type == "array" and not isinstance(params[key], list):
            return False

    return True
