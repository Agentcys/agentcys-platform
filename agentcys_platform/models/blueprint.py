"""Blueprint and BlueprintVersion models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class Blueprint(BaseModel):
    model_config = ConfigDict()

    blueprint_id: str
    name: str
    description: str
    latest_version: str

    def to_firestore(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "name": self.name,
            "description": self.description,
            "latest_version": self.latest_version,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> Blueprint:
        return cls(
            blueprint_id=doc["blueprint_id"],
            name=doc["name"],
            description=doc["description"],
            latest_version=doc["latest_version"],
        )


class BlueprintVersion(BaseModel):
    model_config = ConfigDict()

    blueprint_id: str
    version: str
    tf_module_uri: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    published_at: datetime
    immutable: bool = True

    def to_firestore(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "version": self.version,
            "tf_module_uri": self.tf_module_uri,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "published_at": self.published_at.isoformat(),
            "immutable": self.immutable,
        }

    @classmethod
    def from_firestore(cls, doc: dict[str, Any]) -> BlueprintVersion:
        published_at = doc["published_at"]
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at)
        return cls(
            blueprint_id=doc["blueprint_id"],
            version=doc["version"],
            tf_module_uri=doc["tf_module_uri"],
            input_schema=doc["input_schema"],
            output_schema=doc["output_schema"],
            published_at=published_at,
            immutable=doc.get("immutable", True),
        )
