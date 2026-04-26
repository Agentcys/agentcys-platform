from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentcys_platform.config import get_settings
from agentcys_platform.models.blueprint import Blueprint, BlueprintVersion
from agentcys_platform.store.firestore import (
    COLLECTION_BLUEPRINTS,
    COLLECTION_BLUEPRINT_VERSIONS,
)

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "blueprints"
VERSION = "1.0.0"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_description(readme_path: Path) -> str:
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:
        stripped = line.strip()
        if stripped:
            return stripped
    msg = f"README {readme_path} does not contain a description paragraph"
    raise ValueError(msg)


def _humanize_blueprint_id(blueprint_id: str) -> str:
    return blueprint_id.replace("-", " ").title()


def _build_blueprint_payloads(bucket_name: str) -> list[tuple[Blueprint, BlueprintVersion]]:
    payloads: list[tuple[Blueprint, BlueprintVersion]] = []

    for blueprint_dir in sorted(path for path in BLUEPRINTS_DIR.iterdir() if path.is_dir()):
        blueprint_id = blueprint_dir.name
        input_schema = _load_json(blueprint_dir / "input_schema.json")
        output_schema = _load_json(blueprint_dir / "output_schema.json")
        description = _read_description(blueprint_dir / "README.md")

        blueprint = Blueprint(
            blueprint_id=blueprint_id,
            name=_humanize_blueprint_id(blueprint_id),
            description=description,
            latest_version=VERSION,
        )
        blueprint_version = BlueprintVersion(
            blueprint_id=blueprint_id,
            version=VERSION,
            tf_module_uri=f"gs://{bucket_name}/{blueprint_id}/{VERSION}.tar.gz",
            input_schema=input_schema,
            output_schema=output_schema,
            published_at=datetime.now(UTC),
            immutable=True,
        )
        payloads.append((blueprint, blueprint_version))

    return payloads


async def _write_payloads(project_id: str, payloads: list[tuple[Blueprint, BlueprintVersion]]) -> None:
    from google.cloud import firestore

    client = firestore.AsyncClient(project=project_id)
    try:
        for blueprint, blueprint_version in payloads:
            await client.collection(COLLECTION_BLUEPRINTS).document(blueprint.blueprint_id).set(
                blueprint.to_firestore(),
                merge=True,
            )
            version_doc_id = f"{blueprint_version.blueprint_id}-{blueprint_version.version}"
            await client.collection(COLLECTION_BLUEPRINT_VERSIONS).document(version_doc_id).set(
                blueprint_version.to_firestore(),
                merge=True,
            )
    finally:
        client.close()


def _print_dry_run(payloads: list[tuple[Blueprint, BlueprintVersion]]) -> None:
    for blueprint, blueprint_version in payloads:
        version_doc_id = f"{blueprint_version.blueprint_id}-{blueprint_version.version}"
        print(
            json.dumps(
                {
                    "collection": COLLECTION_BLUEPRINTS,
                    "document_id": blueprint.blueprint_id,
                    "data": blueprint.to_firestore(),
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        print(
            json.dumps(
                {
                    "collection": COLLECTION_BLUEPRINT_VERSIONS,
                    "document_id": version_doc_id,
                    "data": blueprint_version.to_firestore(),
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed first-party blueprint catalog records")
    parser.add_argument("--dry-run", action="store_true", help="Print intended writes without persisting")
    parser.add_argument(
        "--bucket",
        dest="bucket_name",
        default=None,
        help="Override the blueprint artifact bucket name",
    )
    parser.add_argument(
        "--project-id",
        dest="project_id",
        default=None,
        help="Override the Firestore GCP project ID",
    )
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    settings = None
    if not args.dry_run and (args.bucket_name is None or args.project_id is None):
        settings = get_settings()

    bucket_name = args.bucket_name or (settings.BLUEPRINT_BUCKET if settings is not None else "blueprints")
    project_id = args.project_id or (settings.GCP_PROJECT_ID if settings is not None else "dry-run-project")
    payloads = _build_blueprint_payloads(bucket_name)

    if args.dry_run:
        _print_dry_run(payloads)
        return 0

    await _write_payloads(project_id, payloads)
    print(
        f"Seeded {len(payloads)} blueprints into Firestore project {project_id} from {BLUEPRINTS_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))