"""Minimal FastAPI entrypoint for the Cloud Tasks push worker."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response

from agentcys_platform.security.hmac_signer import verify_signature
from worker.config import get_worker_settings
from worker.handler import execute_run

logger = logging.getLogger(__name__)


# ── Client state ──────────────────────────────────────────────────────────────


def _make_firestore_client() -> Any:
    from google.cloud import firestore

    return firestore.AsyncClient()


def _make_gcs_client() -> Any:
    from google.cloud import storage

    return storage.Client()


def _make_secrets_client() -> Any:
    from google.cloud import secretmanager

    return secretmanager.SecretManagerServiceClient()


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    settings = get_worker_settings()
    app.state.settings = settings
    app.state.firestore_client = _make_firestore_client()
    app.state.gcs_client = _make_gcs_client()
    app.state.secrets_client = _make_secrets_client()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Agentcys Deployment Worker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def task_handler(request: Request) -> Response:
    """Receive a Cloud Tasks HTTP-push delivery and execute the deployment run."""
    settings: Any = request.app.state.settings

    sig = request.headers.get("X-Agentcys-Signature", "")
    ts = request.headers.get("X-Agentcys-Timestamp", "")
    body = await request.body()

    if not verify_signature(body, sig, ts, settings.HMAC_SIGNING_SECRET):
        logger.warning("HMAC verification failed for incoming task")
        return Response(content="invalid_signature", status_code=401)

    try:
        import json

        payload = json.loads(body)
        run_id: str = payload["run_id"]
        deployment_id: str = payload["deployment_id"]
    except (KeyError, ValueError) as exc:
        logger.error("Malformed task payload: %s", exc)
        return Response(content="bad_request", status_code=400)

    try:
        await execute_run(
            run_id=run_id,
            deployment_id=deployment_id,
            firestore_client=request.app.state.firestore_client,
            gcs_client=request.app.state.gcs_client,
            secrets_client=request.app.state.secrets_client,
        )
    except Exception:
        logger.exception("execute_run raised an unhandled exception for run_id=%s", run_id)
        return Response(content="internal_error", status_code=500)

    return Response(content="ok", status_code=200)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    settings = get_worker_settings()
    uvicorn.run(
        "worker.main:app",
        host="0.0.0.0",  # noqa: S104 — Cloud Run requires 0.0.0.0
        port=settings.WORKER_PORT,
        log_level="info",
    )
