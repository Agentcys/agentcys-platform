"""Integration tests for the worker FastAPI endpoint."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure required env vars are set before importing worker modules
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("SECRET_MANAGER_PROJECT", "test-project")
os.environ.setdefault("STATE_MIRROR_BUCKET", "test-state-bucket")
os.environ.setdefault("BLUEPRINT_BUCKET", "test-blueprint-bucket")
os.environ.setdefault("CLOUD_TASKS_QUEUE", "test-queue")
os.environ.setdefault("HMAC_SIGNING_SECRET", "test-secret-at-least-32-chars-xxxx")

# ruff: noqa: E402, I001
from agentcys_platform.security.hmac_signer import sign_payload
from worker.config import get_worker_settings

# ── App fixture ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_worker_settings.cache_clear()
    yield
    get_worker_settings.cache_clear()


@pytest.fixture()
def worker_app():
    """Return a TestClient for worker.main with mocked lifespan clients."""
    with (
        patch("worker.main._make_firestore_client") as mock_fs,
        patch("worker.main._make_gcs_client") as mock_gcs,
        patch("worker.main._make_secrets_client") as mock_sec,
    ):
        mock_fs.return_value = MagicMock()
        mock_gcs.return_value = MagicMock()
        mock_sec.return_value = MagicMock()

        from worker.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


_SECRET = "test-secret-at-least-32-chars-xxxx"  # noqa: S105
_PAYLOAD = json.dumps({"run_id": "run-001", "deployment_id": "dep-001"}).encode()


def _valid_headers(payload: bytes = _PAYLOAD) -> dict[str, str]:
    sig, ts = sign_payload(payload, _SECRET)
    return {
        "X-Agentcys-Signature": sig,
        "X-Agentcys-Timestamp": ts,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_post_handler_rejects_invalid_hmac(worker_app: TestClient) -> None:
    response = worker_app.post(
        "/",
        content=_PAYLOAD,
        headers={
            "X-Agentcys-Signature": "deadbeef" * 8,
            "X-Agentcys-Timestamp": "1000000000",
        },
    )
    assert response.status_code == 401


@patch("worker.main.execute_run", new_callable=AsyncMock)
def test_post_handler_accepts_valid_hmac_and_calls_execute_run(
    mock_execute: AsyncMock,
    worker_app: TestClient,
) -> None:
    response = worker_app.post(
        "/",
        content=_PAYLOAD,
        headers=_valid_headers(),
    )
    assert response.status_code == 200
    mock_execute.assert_awaited_once()
    call_kwargs = mock_execute.await_args
    assert call_kwargs.kwargs["run_id"] == "run-001" or call_kwargs.args[0] == "run-001"


@patch("worker.main.execute_run", new_callable=AsyncMock)
@patch("worker.handler.WorkspaceManager")
@patch("worker.handler.TerraformRunner")
@patch("worker.handler.mirror_state")
def test_full_apply_flow(
    mock_mirror: MagicMock,
    mock_runner_cls: MagicMock,
    mock_ws_cls: MagicMock,
    mock_execute: AsyncMock,
    worker_app: TestClient,
) -> None:
    """Verify that a valid HMAC request triggers execute_run without 5xx."""
    mock_execute.return_value = None  # successful no-op

    payload = json.dumps({"run_id": "run-full", "deployment_id": "dep-full"}).encode()
    headers = _valid_headers(payload)

    response = worker_app.post("/", content=payload, headers=headers)

    assert response.status_code == 200
    mock_execute.assert_awaited_once()
