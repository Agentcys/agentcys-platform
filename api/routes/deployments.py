"""Deployment routes for v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from agentcys_platform.config import get_settings
from api.middleware.auth import get_request_api_key_id, get_request_tenant_id
from api.services.deployment_service import DeploymentService

router = APIRouter(tags=["deployments"])


class CreateDeploymentRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    blueprint_id: str = Field(min_length=1, max_length=100)
    blueprint_version: str | None = Field(default=None, min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)


class DeploymentRunView(BaseModel):
    run_id: str
    deployment_id: str
    operation: str
    status: str
    actor: dict[str, Any]


class DeploymentView(BaseModel):
    deployment_id: str
    tenant_id: str
    project_id: str
    blueprint_id: str
    blueprint_version: str
    name: str
    params: dict[str, Any]
    outputs: dict[str, Any] | None = None
    status: str
    created_at: str
    updated_at: str
    current_run_id: str | None = None


class DeploymentDetailResponse(BaseModel):
    deployment: DeploymentView
    current_run: DeploymentRunView | None = None


class DeploymentListResponse(BaseModel):
    items: list[DeploymentView]
    pagination: dict[str, int]


@router.post(
    "/deployments", response_model=DeploymentDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_deployment(
    payload: CreateDeploymentRequest,
    request: Request,
) -> DeploymentDetailResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    tenant_id = get_request_tenant_id(request)
    api_key_id = get_request_api_key_id(request)
    actor = {"type": "api_key", "id": api_key_id}

    service = DeploymentService(db, get_settings())
    try:
        deployment, run = await service.create_deployment(
            tenant_id=tenant_id,
            actor=actor,
            project_id=payload.project_id,
            blueprint_id=payload.blueprint_id,
            blueprint_version=payload.blueprint_version,
            name=payload.name,
            params=payload.params,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 422
        if detail in {"project_not_found", "blueprint_not_found", "blueprint_version_not_found"}:
            code = 404
        raise HTTPException(status_code=code, detail={"error": detail}) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error": str(exc)}) from exc

    return DeploymentDetailResponse(
        deployment=DeploymentView(**deployment.to_firestore()),
        current_run=DeploymentRunView(**run.to_firestore()),
    )


@router.get("/deployments/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(deployment_id: str, request: Request) -> DeploymentDetailResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    tenant_id = get_request_tenant_id(request)
    service = DeploymentService(db, get_settings())

    try:
        result = await service.get_deployment(tenant_id=tenant_id, deployment_id=deployment_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error": str(exc)}) from exc

    if result is None:
        raise HTTPException(status_code=404, detail={"error": "deployment_not_found"})

    return DeploymentDetailResponse(
        deployment=DeploymentView(**result["deployment"]),
        current_run=(DeploymentRunView(**result["current_run"]) if result["current_run"] else None),
    )


@router.get("/deployments", response_model=DeploymentListResponse)
async def list_deployments(
    request: Request,
    project_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DeploymentListResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    tenant_id = get_request_tenant_id(request)
    service = DeploymentService(db, get_settings())
    result = await service.list_deployments(
        tenant_id=tenant_id,
        project_id=project_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return DeploymentListResponse(
        items=[DeploymentView(**item) for item in result["items"]],
        pagination=result["pagination"],
    )


@router.delete("/deployments/{deployment_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_deployment(deployment_id: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    tenant_id = get_request_tenant_id(request)
    api_key_id = get_request_api_key_id(request)
    actor = {"type": "api_key", "id": api_key_id}

    service = DeploymentService(db, get_settings())
    try:
        deployment, run = await service.destroy_deployment(
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 422
        if detail == "deployment_not_found":
            code = 404
        raise HTTPException(status_code=code, detail={"error": detail}) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error": str(exc)}) from exc

    return {
        "deployment_id": deployment["deployment_id"],
        "status": deployment["status"],
        "run_id": run.run_id,
        "queued": True,
    }
