"""Agentcys Platform API — FastAPI application entry point.

Middleware stack (outermost → innermost):
  1. RequestBodySizeLimitMiddleware — rejects bodies > REQUEST_MAX_BODY_BYTES
  2. CORSMiddleware — handles preflight and cross-origin headers
  3. SecurityHeadersMiddleware — HSTS, X-Frame-Options, CSP (report-only)
  4. FetchMetadataCsrfMiddleware — blocks cross-site write requests

Startup:
  - APP_ENV is validated via Settings (hard-fails on unknown values)
  - Firestore AsyncClient is initialised and stored on app.state

Routes:
  - GET /health  — liveness probe (no auth)
  - (Future) api/routes/ modules mounted in Prompt 2
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentcys_platform.config import get_settings
from agentcys_platform.security.http_security import (
    FetchMetadataCsrfMiddleware,
    RequestBodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from api.middleware.auth import APIKeyAuthMiddleware
from api.routes import blueprints, credentials, deployments, projects, tenants

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared resources on startup; clean up on shutdown."""
    settings = get_settings()

    # ── Firestore client ─────────────────────────────────────────────────
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        logger.info("Firestore emulator detected at %s", os.getenv("FIRESTORE_EMULATOR_HOST"))

    try:
        from google.cloud import firestore  # type: ignore[import]

        db = firestore.AsyncClient(project=settings.GCP_PROJECT_ID)
        app.state.db = db
        logger.info(
            "Firestore AsyncClient initialised (project=%s, env=%s)",
            settings.GCP_PROJECT_ID,
            settings.APP_ENV,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Firestore client init failed (non-fatal in local dev): %s", exc)
        app.state.db = None

    yield

    # ── Cleanup ─────────────────────────────────────────────────────────
    if getattr(app.state, "db", None) is not None:
        try:
            app.state.db.close()
        except Exception:  # pragma: no cover  # noqa: S110
            logger.debug("Firestore client close failed on shutdown")


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Separated from module-level instantiation so tests can call this
    directly and get a fresh app with a clean state.
    """
    settings = get_settings()

    app = FastAPI(
        title="Agentcys Platform API",
        version="0.1.0",
        description=(
            "Multi-tenant GCP infrastructure deployment control plane. "
            "Agents provision Cloud Run, GCS, and other GCP resources via "
            "declarative Terraform blueprints."
        ),
        lifespan=lifespan,
        # Disable default /docs and /redoc in production
        docs_url=None if settings.is_prod() else "/docs",
        redoc_url=None if settings.is_prod() else "/redoc",
    )

    cors_origins = settings.get_cors_origins()

    # ── Middleware ───────────────────────────────────────────────────────
    # Order matters: added last = outermost (wraps all inner layers).

    # 4. CSRF (innermost of the security stack)
    app.add_middleware(FetchMetadataCsrfMiddleware, allowed_origins=cors_origins)

    # 3. Security headers
    platform_origin = cors_origins[0] if cors_origins else ""
    app.add_middleware(SecurityHeadersMiddleware, platform_origin=platform_origin)

    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-Agentcys-Signature",
            "X-Agentcys-Timestamp",
        ],
        allow_credentials=True,
        max_age=600,
    )

    # 1. Body size limit (outermost — fires before anything parses the body)
    app.add_middleware(
        RequestBodySizeLimitMiddleware,
        max_bytes=settings.REQUEST_MAX_BODY_BYTES,
    )

    # 0. API key auth for v1 tenant-scoped endpoints
    app.add_middleware(APIKeyAuthMiddleware)

    # ── Routes ──────────────────────────────────────────────────────────
    app.include_router(tenants.router, prefix="/v1")
    app.include_router(credentials.router, prefix="/v1")
    app.include_router(projects.router, prefix="/v1")
    app.include_router(blueprints.router, prefix="/v1")
    app.include_router(deployments.router, prefix="/v1")

    @app.get("/health", tags=["ops"], summary="Liveness probe")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "env": settings.APP_ENV,
            "version": "0.1.0",
        }

    return app


# ── Module-level app instance (used by uvicorn) ───────────────────────────────
app = create_app()
