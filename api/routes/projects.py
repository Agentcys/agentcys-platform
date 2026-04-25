"""Customer project routes for v1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.middleware.auth import get_request_tenant_id
from api.services.project_service import ProjectService

router = APIRouter(tags=["projects"])


class CreateProjectRequest(BaseModel):
    gcp_project_id: str = Field(min_length=1, max_length=200)
    credential_id: str = Field(min_length=1, max_length=64)
    default_region: str = Field(min_length=1, max_length=64)
    state_bucket: str = Field(min_length=3, max_length=63)


class ProjectResponse(BaseModel):
    project_id: str
    tenant_id: str
    gcp_project_id: str
    credential_id: str
    default_region: str
    state_bucket: str
    status: str
    created_at: str


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: CreateProjectRequest, request: Request) -> ProjectResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    tenant_id = get_request_tenant_id(request)
    service = ProjectService(db)

    try:
        project = await service.link_project(
            tenant_id=tenant_id,
            gcp_project_id=payload.gcp_project_id,
            credential_id=payload.credential_id,
            default_region=payload.default_region,
            state_bucket=payload.state_bucket,
        )
    except ValueError as exc:
        if str(exc) == "credential_not_found":
            raise HTTPException(status_code=404, detail={"error": "credential_not_found"}) from exc
        raise HTTPException(status_code=422, detail={"error": str(exc)}) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error": str(exc)}) from exc

    return ProjectResponse(
        project_id=project.project_id,
        tenant_id=project.tenant_id,
        gcp_project_id=project.gcp_project_id,
        credential_id=project.credential_id,
        default_region=project.default_region,
        state_bucket=project.state_bucket,
        status=project.status,
        created_at=project.created_at.isoformat(),
    )
