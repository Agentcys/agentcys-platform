"""Service layer for blueprint catalog queries."""

from __future__ import annotations

from typing import Any

_BLUEPRINTS_COLLECTION = "blueprints"
_BLUEPRINT_VERSIONS_COLLECTION = "blueprint_versions"


class BlueprintService:
    """Read-only operations for blueprint catalog data."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def list_blueprints(self, *, limit: int = 200) -> list[dict[str, Any]]:
        docs = await self._db.collection(_BLUEPRINTS_COLLECTION).limit(limit).get()
        result: list[dict[str, Any]] = []

        for snap in docs:
            if not snap.exists:
                continue
            doc = snap.to_dict()
            latest_version = await self._get_version(
                blueprint_id=str(doc.get("blueprint_id")),
                version=str(doc.get("latest_version")),
            )
            result.append({**doc, "latest": latest_version})

        return result

    async def get_blueprint_with_latest(self, *, blueprint_id: str) -> dict[str, Any] | None:
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

        blueprint = snap.to_dict()
        latest_version = await self._get_version(
            blueprint_id=blueprint_id,
            version=str(blueprint.get("latest_version")),
        )
        return {**blueprint, "latest": latest_version}

    async def _get_version(self, *, blueprint_id: str, version: str) -> dict[str, Any] | None:
        version_docs = (
            await self._db.collection(_BLUEPRINT_VERSIONS_COLLECTION)
            .where(filter=("blueprint_id", "==", blueprint_id))
            .where(filter=("version", "==", version))
            .limit(1)
            .get()
        )
        if not version_docs:
            return None

        snap = version_docs[0]
        if not snap.exists:
            return None
        return snap.to_dict()
