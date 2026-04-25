"""Integration tests — HTTP security middleware stack.

Tests run against a minimal FastAPI app wired with the same middleware
stack used in api/main.py so we validate real HTTP behaviour.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from agentcys_platform.security.http_security import (
    FetchMetadataCsrfMiddleware,
    RequestBodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
)

ALLOWED_ORIGIN = "http://localhost:3000"


def _build_app(max_body_bytes: int = 1_048_576) -> FastAPI:
    """Build a minimal app wired with the platform middleware stack."""
    app = FastAPI()

    # Same order as api/main.py
    app.add_middleware(RequestBodySizeLimitMiddleware, max_bytes=max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.add_middleware(SecurityHeadersMiddleware, platform_origin=ALLOWED_ORIGIN)
    app.add_middleware(FetchMetadataCsrfMiddleware, allowed_origins=[ALLOWED_ORIGIN])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/data")
    async def post_data():
        return {"received": True}

    return app


@pytest.fixture()
def client():
    return TestClient(_build_app(), raise_server_exceptions=False)


@pytest.fixture()
def tiny_client():
    """Client with a 10-byte body limit for size-limit tests."""
    return TestClient(_build_app(max_body_bytes=10), raise_server_exceptions=False)


# ── Security headers ─────────────────────────────────────────────────────────


class TestSecurityHeaders:
    def test_x_content_type_options(self, client):
        r = client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, client):
        r = client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY"

    def test_hsts_present(self, client):
        r = client.get("/health")
        hsts = r.headers.get("strict-transport-security", "")
        assert "max-age=" in hsts

    def test_csp_report_only_present(self, client):
        r = client.get("/health")
        csp = r.headers.get("content-security-policy-report-only", "")
        assert "default-src" in csp
        assert "frame-ancestors" in csp

    def test_referrer_policy(self, client):
        r = client.get("/health")
        assert "referrer-policy" in r.headers


# ── CSRF middleware ───────────────────────────────────────────────────────────


class TestCsrfMiddleware:
    def test_get_request_is_always_allowed(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_post_with_allowed_origin_succeeds(self, client):
        r = client.post("/data", headers={"Origin": ALLOWED_ORIGIN})
        assert r.status_code == 200

    def test_post_with_disallowed_origin_is_rejected(self, client):
        r = client.post("/data", headers={"Origin": "https://evil.example.com"})
        assert r.status_code == 403
        body = r.json()
        assert body["detail"]["error"] == "csrf_origin_denied"

    def test_post_without_origin_from_trusted_referer_succeeds(self, client):
        r = client.post("/data", headers={"Referer": f"{ALLOWED_ORIGIN}/page"})
        assert r.status_code == 200

    def test_post_with_untrusted_referer_is_rejected(self, client):
        r = client.post("/data", headers={"Referer": "https://evil.example.com/page"})
        assert r.status_code == 403
        assert r.json()["detail"]["error"] == "csrf_referer_denied"

    def test_post_cross_site_fetch_metadata_is_rejected(self, client):
        r = client.post(
            "/data",
            headers={
                "Sec-Fetch-Site": "cross-site",
                # No Origin or Referer
            },
        )
        assert r.status_code == 403

    def test_post_same_origin_fetch_metadata_succeeds(self, client):
        r = client.post(
            "/data",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Sec-Fetch-Site": "same-origin",
            },
        )
        assert r.status_code == 200

    def test_post_invalid_sec_fetch_site_is_rejected(self, client):
        r = client.post(
            "/data",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Sec-Fetch-Site": "invalid-value",
            },
        )
        assert r.status_code == 403
        assert r.json()["detail"]["error"] == "csrf_fetch_metadata_invalid"

    def test_machine_client_no_origin_no_referer_no_sec_fetch_succeeds(self, client):
        """API-to-API calls (curl, SDK) without browser headers must pass."""
        r = client.post("/data")
        assert r.status_code == 200


# ── Body size limit ───────────────────────────────────────────────────────────


class TestBodySizeLimit:
    def test_small_body_is_accepted(self, tiny_client):
        r = tiny_client.post(
            "/data",
            headers={"Origin": ALLOWED_ORIGIN, "Content-Length": "5"},
            content=b"hello",
        )
        assert r.status_code == 200

    def test_oversized_body_is_rejected(self, tiny_client):
        big = b"x" * 100
        r = tiny_client.post(
            "/data",
            headers={"Origin": ALLOWED_ORIGIN},
            content=big,
        )
        assert r.status_code == 413
        assert r.json()["detail"]["error"] == "request_body_too_large"
