"""Credential upload routes for v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from agentcys_platform.config import get_settings
from api.middleware.auth import get_request_tenant_id
from api.services.credential_service import CredentialService

router = APIRouter(tags=["credentials"])


class CreateCredentialRequest(BaseModel):
    sa_key: dict[str, Any] = Field(default_factory=dict)


class CredentialResponse(BaseModel):
    credential_id: str
    tenant_id: str
    kind: str
    sa_email: str
    created_at: str


@router.post("/credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CreateCredentialRequest, request: Request
) -> CredentialResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    tenant_id = get_request_tenant_id(request)
    service = CredentialService(db, get_settings())

    try:
        credential = await service.create_credential(tenant_id=tenant_id, sa_key=payload.sa_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)}) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error": str(exc)}) from exc

    return CredentialResponse(
        credential_id=credential.credential_id,
        tenant_id=credential.tenant_id,
        kind=credential.kind,
        sa_email=credential.sa_email,
        created_at=credential.created_at.isoformat(),
    )
