"""Tenant management routes for v1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.services.tenant_service import TenantService

router = APIRouter(tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    plan: str = Field(default="free", pattern="^(free|pro|enterprise)$")


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    plan: str
    created_at: str


class CreateAPIKeyRequest(BaseModel):
    label: str | None = Field(default=None, max_length=200)


class APIKeyResponse(BaseModel):
    key_id: str
    tenant_id: str
    api_key: str
    created_at: str


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: CreateTenantRequest, request: Request) -> TenantResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    service = TenantService(db)
    tenant = await service.create_tenant(name=payload.name, plan=payload.plan)

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        plan=tenant.plan,
        created_at=tenant.created_at.isoformat(),
    )


@router.post(
    "/tenants/{tenant_id}/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    tenant_id: str,
    payload: CreateAPIKeyRequest,
    request: Request,
) -> APIKeyResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    service = TenantService(db)
    try:
        created = await service.create_api_key(tenant_id=tenant_id, label=payload.label)
    except ValueError as exc:
        if str(exc) == "tenant_not_found":
            raise HTTPException(status_code=404, detail={"error": "tenant_not_found"}) from exc
        raise

    return APIKeyResponse(**created)
