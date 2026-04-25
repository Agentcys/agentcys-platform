"""HTTP security middleware for the Agentcys Platform.

Provides:
- ``FetchMetadataCsrfMiddleware`` — Fetch Metadata based CSRF protection for
  state-changing requests (POST / PUT / PATCH / DELETE).
- ``SecurityHeadersMiddleware`` — adds HSTS, X-Frame-Options, CSP (report-only),
  and other defensive headers to every response.
- ``RequestBodySizeLimitMiddleware`` — enforces ``REQUEST_MAX_BODY_BYTES``.

Middleware order in api/main.py (outermost to innermost):
  1. RequestBodySizeLimitMiddleware
  2. CORSMiddleware  (FastAPI built-in)
  3. SecurityHeadersMiddleware
  4. FetchMetadataCsrfMiddleware
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_VALID_SEC_FETCH_SITE_VALUES = {"cross-site", "same-origin", "same-site", "none"}


def _normalized_origin(value: str) -> str:
    return value.strip().rstrip("/")


def _origin_from_referer(referer: str) -> str:
    parsed = urlsplit(referer)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return _normalized_origin(f"{parsed.scheme}://{parsed.netloc}")


def _is_allowed_origin(origin: str, allowed_origins: list[str]) -> bool:
    normalized = _normalized_origin(origin)
    if not normalized:
        return False
    return normalized in allowed_origins


def build_security_headers(platform_origin: str = "") -> dict[str, str]:
    """Return the defensive HTTP response headers for the platform.

    CSP is report-only so violations surface in Cloud Logging before we
    switch to enforcement mode.
    """
    connect_src = "'self'"
    if platform_origin:
        connect_src = f"'self' {platform_origin}"

    return {
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
        "Content-Security-Policy-Report-Only": "; ".join(
            [
                "default-src 'self'",
                f"connect-src {connect_src}",
                "base-uri 'self'",
                "frame-ancestors 'none'",
                "form-action 'self'",
                "object-src 'none'",
                "script-src 'self'",
            ]
        ),
    }


class FetchMetadataCsrfMiddleware(BaseHTTPMiddleware):
    """Reject cross-site write requests that lack a trusted Origin/Referer.

    Relies on the Fetch Metadata ``Sec-Fetch-Site`` header where available,
    falling back to Origin and Referer validation for older clients.

    Machine-to-machine clients (curl, Python httpx, SDK calls) never send
    ``Sec-Fetch-Site``, so they are not blocked — only browser-initiated
    cross-site writes are stopped.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self._allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() in _SAFE_METHODS:
            return await call_next(request)

        origin = _normalized_origin(request.headers.get("origin", ""))
        referer_origin = _origin_from_referer(request.headers.get("referer", ""))
        sec_fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()

        trusted_origin = False

        if origin:
            trusted_origin = _is_allowed_origin(origin, self._allowed_origins)
            if not trusted_origin:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": {
                            "error": "csrf_origin_denied",
                            "detail": f"Origin '{origin}' is not allowed for write requests",
                        }
                    },
                )
        elif referer_origin:
            trusted_origin = _is_allowed_origin(referer_origin, self._allowed_origins)
            if not trusted_origin:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": {
                            "error": "csrf_referer_denied",
                            "detail": (
                                f"Referer origin '{referer_origin}' is not allowed for write "
                                "requests"
                            ),
                        }
                    },
                )

        if sec_fetch_site and sec_fetch_site not in _VALID_SEC_FETCH_SITE_VALUES:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": {
                        "error": "csrf_fetch_metadata_invalid",
                        "detail": f"Unsupported Sec-Fetch-Site value '{sec_fetch_site}'",
                    }
                },
            )

        if sec_fetch_site == "cross-site" and not trusted_origin:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": {
                        "error": "csrf_cross_site_denied",
                        "detail": "Cross-site write requests require an allowed Origin or Referer",
                    }
                },
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive security headers to every response."""

    def __init__(self, app: ASGIApp, platform_origin: str = "") -> None:
        super().__init__(app)
        self._headers = build_security_headers(platform_origin)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in self._headers.items():
            response.headers.setdefault(name, value)
        return response


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds *max_bytes*.

    Must be the outermost middleware so it fires before body parsing.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": {
                                "error": "request_body_too_large",
                                "detail": (
                                    f"Request body exceeds the {self._max_bytes}-byte limit"
                                ),
                            }
                        },
                    )
            except ValueError:
                pass  # malformed Content-Length — let FastAPI handle it

        return await call_next(request)
