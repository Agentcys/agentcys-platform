"""Unit tests for worker.handler.execute_run."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure required env vars are set before importing worker modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("SECRET_MANAGER_PROJECT", "test-project")
os.environ.setdefault("STATE_MIRROR_BUCKET", "test-state-bucket")
os.environ.setdefault("BLUEPRINT_BUCKET", "test-blueprint-bucket")
os.environ.setdefault("CLOUD_TASKS_QUEUE", "test-queue")
os.environ.setdefault("HMAC_SIGNING_SECRET", "test-secret-at-least-32-chars-xxxx")
os.environ.setdefault("APP_ENV", "test")

from worker.config import get_worker_settings  # noqa: E402
from worker.handler import execute_run  # noqa: E402


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache so each test gets a fresh WorkerSettings."""
    get_worker_settings.cache_clear()
    yield
    get_worker_settings.cache_clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _iso() -> str:
    return datetime.now(UTC).isoformat()


def _run_doc(status: str = "queued", operation: str = "apply") -> dict[str, Any]:
    return {
        "run_id": "run-001",
        "deployment_id": "dep-001",
        "operation": operation,
        "status": status,
        "actor": {"type": "user", "id": "user-abc"},
    }


def _dep_doc() -> dict[str, Any]:
    return {
        "deployment_id": "dep-001",
        "tenant_id": "tenant-001",
        "project_id": "proj-001",
        "blueprint_id": "bp-001",
        "blueprint_version": "v1",
        "name": "my-deployment",
        "params": {"zone": "us-central1-a"},
        "status": "pending",
        "created_at": _iso(),
        "updated_at": _iso(),
    }


def _project_doc() -> dict[str, Any]:
    return {
        "project_id": "proj-001",
        "gcp_project_id": "gcp-proj-001",
        "tenant_id": "tenant-001",
        "default_region": "us-central1",
        "credential_id": "cred-001",
        "state_bucket": "my-state-bucket",
        "created_at": _iso(),
        "status": "linked",
    }


def _cred_doc() -> dict[str, Any]:
    return {
        "credential_id": "cred-001",
        "tenant_id": "tenant-001",
        "kind": "sa_key",
        "secret_manager_uri": "projects/p/secrets/s/versions/latest",
        "sa_email": "sa@project.iam.gserviceaccount.com",
        "created_at": _iso(),
    }


def _bpv_doc() -> dict[str, Any]:
    return {
        "blueprint_id": "bp-001",
        "version": "v1",
        "tf_module_uri": "gs://blueprints/bp-001/v1/module.tar.gz",
        "input_schema": {},
        "output_schema": {},
        "published_at": _iso(),
        "immutable": True,
    }


def _make_fake_firestore(docs: dict[str, dict[str, Any]]) -> MagicMock:
    """Build a fake Firestore client that returns documents from *docs*.

    Keys are ``collection/doc_id``.
    """
    updates: dict[str, dict[str, Any]] = {}

    class FakeSnap:
        def __init__(self, data: dict[str, Any] | None) -> None:
            self._data = data
            self.exists = data is not None

        def to_dict(self) -> dict[str, Any]:
            return dict(self._data) if self._data else {}

    class FakeDocRef:
        def __init__(self, key: str) -> None:
            self._key = key

        async def get(self) -> FakeSnap:
            return FakeSnap(docs.get(self._key))

        async def update(self, upd: dict[str, Any]) -> None:
            updates[self._key] = upd

    class FakeCollection:
        def __init__(self, name: str) -> None:
            self._name = name

        def document(self, doc_id: str) -> FakeDocRef:
            return FakeDocRef(f"{self._name}/{doc_id}")

    client = MagicMock()
    client.collection.side_effect = lambda name: FakeCollection(name)
    client._updates = updates
    return client


def _make_secrets_client(sa_key_data: dict[str, Any] = None) -> MagicMock:
    if sa_key_data is None:
        sa_key_data = {"type": "service_account", "project_id": "gcp-proj-001"}
    client = MagicMock()
    resp = MagicMock()
    resp.payload.data = json.dumps(sa_key_data).encode()
    client.access_secret_version.return_value = resp
    return client


def _make_gcs_client() -> MagicMock:
    bucket = MagicMock()
    blob = MagicMock()
    blob.download_to_filename = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    return client


def _make_mock_workspace(mock_ws_cls: MagicMock) -> MagicMock:
    """Configure a mock WorkspaceManager for handler tests."""
    fake_dir = Path("/nonexistent/fake-run")  # noqa: S108
    ws = MagicMock()
    ws.workspace_dir = fake_dir
    ws.create.return_value = fake_dir
    ws.write_sa_key.return_value = fake_dir / "sa_key.json"
    ws.download_module.return_value = fake_dir / "module"
    mock_ws_cls.return_value = ws
    return ws


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_run_idempotent_when_not_queued() -> None:
    """If run status is not 'queued', execute_run returns immediately."""
    docs = {
        "deployment_runs/run-001": _run_doc(status="succeeded"),
    }
    fs = _make_fake_firestore(docs)

    await execute_run("run-001", "dep-001", fs, MagicMock(), MagicMock())

    # No update should have been called since we returned early
    assert not fs._updates


@pytest.mark.asyncio
@patch("worker.handler.WorkspaceManager")
@patch("worker.handler.TerraformRunner")
@patch("worker.handler.mirror_state")
async def test_execute_run_apply_happy_path(
    mock_mirror: MagicMock,
    mock_runner_cls: MagicMock,
    mock_ws_cls: MagicMock,
) -> None:
    """Happy path: apply operation succeeds end-to-end."""
    docs = {
        "deployment_runs/run-001": _run_doc(status="queued", operation="apply"),
        "deployments/dep-001": _dep_doc(),
        "customer_projects/proj-001": _project_doc(),
        "customer_credentials/cred-001": _cred_doc(),
        "blueprint_versions/bp-001:v1": _bpv_doc(),
    }
    fs = _make_fake_firestore(docs)

    ws = _make_mock_workspace(mock_ws_cls)

    # Mock runner with success
    runner = MagicMock()
    runner.init.return_value = MagicMock(returncode=0)
    runner.plan.return_value = MagicMock(returncode=0)
    runner.apply.return_value = MagicMock(returncode=0)
    runner.output_json.return_value = {"vpc_id": {"value": "vpc-abc"}}
    mock_runner_cls.return_value = runner

    secrets = _make_secrets_client()
    gcs = _make_gcs_client()

    await execute_run("run-001", "dep-001", fs, gcs, secrets)

    runner.init.assert_called_once()
    runner.plan.assert_called_once()
    runner.apply.assert_called_once()
    runner.output_json.assert_called_once()
    mock_mirror.assert_called_once()
    ws.cleanup.assert_called_once()


@pytest.mark.asyncio
@patch("worker.handler.WorkspaceManager")
@patch("worker.handler.TerraformRunner")
@patch("worker.handler.mirror_state")
async def test_execute_run_marks_failed_on_init_error(
    mock_mirror: MagicMock,
    mock_runner_cls: MagicMock,
    mock_ws_cls: MagicMock,
) -> None:
    docs = {
        "deployment_runs/run-001": _run_doc(status="queued"),
        "deployments/dep-001": _dep_doc(),
        "customer_projects/proj-001": _project_doc(),
        "customer_credentials/cred-001": _cred_doc(),
        "blueprint_versions/bp-001:v1": _bpv_doc(),
    }
    fs = _make_fake_firestore(docs)

    ws = _make_mock_workspace(mock_ws_cls)

    runner = MagicMock()
    runner.init.return_value = MagicMock(returncode=1, stderr=b"Error: backend init failed")
    mock_runner_cls.return_value = runner

    await execute_run("run-001", "dep-001", fs, _make_gcs_client(), _make_secrets_client())

    runner.plan.assert_not_called()
    ws.cleanup.assert_called()


@pytest.mark.asyncio
@patch("worker.handler.WorkspaceManager")
@patch("worker.handler.TerraformRunner")
@patch("worker.handler.mirror_state")
async def test_execute_run_marks_failed_on_apply_error(
    mock_mirror: MagicMock,
    mock_runner_cls: MagicMock,
    mock_ws_cls: MagicMock,
) -> None:
    docs = {
        "deployment_runs/run-001": _run_doc(status="queued", operation="apply"),
        "deployments/dep-001": _dep_doc(),
        "customer_projects/proj-001": _project_doc(),
        "customer_credentials/cred-001": _cred_doc(),
        "blueprint_versions/bp-001:v1": _bpv_doc(),
    }
    fs = _make_fake_firestore(docs)

    ws = _make_mock_workspace(mock_ws_cls)

    runner = MagicMock()
    runner.init.return_value = MagicMock(returncode=0)
    runner.plan.return_value = MagicMock(returncode=0)
    runner.apply.return_value = MagicMock(returncode=1, stderr=b"Apply failed: quota exceeded")
    mock_runner_cls.return_value = runner

    await execute_run("run-001", "dep-001", fs, _make_gcs_client(), _make_secrets_client())

    runner.output_json.assert_not_called()
    mock_mirror.assert_not_called()
    ws.cleanup.assert_called()


@pytest.mark.asyncio
@patch("worker.handler.WorkspaceManager")
@patch("worker.handler.TerraformRunner")
@patch("worker.handler.mirror_state")
async def test_execute_run_destroy_happy_path(
    mock_mirror: MagicMock,
    mock_runner_cls: MagicMock,
    mock_ws_cls: MagicMock,
) -> None:
    docs = {
        "deployment_runs/run-001": _run_doc(status="queued", operation="destroy"),
        "deployments/dep-001": _dep_doc(),
        "customer_projects/proj-001": _project_doc(),
        "customer_credentials/cred-001": _cred_doc(),
        "blueprint_versions/bp-001:v1": _bpv_doc(),
    }
    fs = _make_fake_firestore(docs)

    ws = _make_mock_workspace(mock_ws_cls)

    runner = MagicMock()
    runner.init.return_value = MagicMock(returncode=0)
    runner.destroy.return_value = MagicMock(returncode=0)
    mock_runner_cls.return_value = runner

    await execute_run("run-001", "dep-001", fs, _make_gcs_client(), _make_secrets_client())

    runner.destroy.assert_called_once()
    runner.plan.assert_not_called()
    runner.apply.assert_not_called()
    mock_mirror.assert_called_once()
    ws.cleanup.assert_called_once()
