"""Blueprint catalog routes for v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.services.blueprint_service import BlueprintService

router = APIRouter(tags=["blueprints"])


class BlueprintVersionView(BaseModel):
    blueprint_id: str
    version: str
    tf_module_uri: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    published_at: str
    immutable: bool = True


class BlueprintView(BaseModel):
    blueprint_id: str
    name: str
    description: str
    latest_version: str
    latest: BlueprintVersionView | None = None


class BlueprintListResponse(BaseModel):
    items: list[BlueprintView]


@router.get("/blueprints", response_model=BlueprintListResponse)
async def list_blueprints(request: Request) -> BlueprintListResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    service = BlueprintService(db)
    items = await service.list_blueprints()
    return BlueprintListResponse(items=[BlueprintView(**item) for item in items])


@router.get("/blueprints/{blueprint_id}", response_model=BlueprintView)
async def get_blueprint(blueprint_id: str, request: Request) -> BlueprintView:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail={"error": "firestore_unavailable"})

    service = BlueprintService(db)
    item = await service.get_blueprint_with_latest(blueprint_id=blueprint_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"error": "blueprint_not_found"})
    return BlueprintView(**item)
