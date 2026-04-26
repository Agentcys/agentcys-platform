"""Unit tests for worker.terraform.workspace.WorkspaceManager."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker.terraform.workspace import WorkspaceManager


@pytest.fixture()
def tmp_base(tmp_path: Path) -> Path:
    return tmp_path / "runs"


@pytest.fixture()
def manager(tmp_base: Path) -> WorkspaceManager:
    return WorkspaceManager(run_id="run-test-001", runs_base_dir=str(tmp_base))


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_create_creates_directory(manager: WorkspaceManager) -> None:
    result = manager.create()
    assert result.is_dir()
    assert result == manager.workspace_dir


def test_write_tfvars_merges_params_and_extra(manager: WorkspaceManager, tmp_base: Path) -> None:
    manager.create()
    (manager.workspace_dir / "module").mkdir(parents=True, exist_ok=True)

    params = {"instance_type": "n2-standard-2", "zone": "us-central1-a"}
    extra = {"project_id": "gcp-proj-123", "region": "us-central1"}

    path = manager.write_tfvars(params, extra)

    assert path.exists()
    data = json.loads(path.read_text())
    assert data["instance_type"] == "n2-standard-2"
    assert data["project_id"] == "gcp-proj-123"
    # extra keys override params when duplicate
    merged_override = {"region": "us-central1", "region_override": "eu-west1"}
    params2 = {"region": "original"}
    path2 = manager.write_tfvars(params2, merged_override)
    data2 = json.loads(path2.read_text())
    assert data2["region"] == "us-central1"


def test_write_backend_tf_creates_file_with_correct_content(
    manager: WorkspaceManager,
) -> None:
    manager.create()
    (manager.workspace_dir / "module").mkdir(parents=True, exist_ok=True)

    manager.write_backend_tf(state_bucket="my-state-bucket", deployment_id="dep-xyz")

    backend = manager.workspace_dir / "module" / "backend.tf"
    assert backend.exists()
    content = backend.read_text()
    assert 'bucket = "my-state-bucket"' in content
    assert 'prefix = "terraform/state/dep-xyz"' in content
    assert 'backend "gcs"' in content


def test_write_provider_tf_creates_file_with_correct_content(
    manager: WorkspaceManager,
    tmp_path: Path,
) -> None:
    manager.create()
    (manager.workspace_dir / "module").mkdir(parents=True, exist_ok=True)

    sa_key_path = tmp_path / "sa_key.json"
    sa_key_path.write_text("{}", encoding="utf-8")

    manager.write_provider_tf(sa_key_path)

    provider = manager.workspace_dir / "module" / "provider.tf"
    assert provider.exists()
    content = provider.read_text()
    assert 'provider "google"' in content
    assert str(sa_key_path.resolve()) in content


def test_cleanup_removes_directory(manager: WorkspaceManager) -> None:
    manager.create()
    assert manager.workspace_dir.is_dir()

    manager.cleanup()

    assert not manager.workspace_dir.exists()


def test_cleanup_is_idempotent(manager: WorkspaceManager) -> None:
    """cleanup() must not raise if the directory is already gone."""
    manager.cleanup()  # dir was never created
