"""API key authentication middleware for tenant-scoped v1 endpoints."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter

_API_KEY_HEADER = "X-API-Key"
_TENANT_KEYS_COLLECTION = "tenant_api_keys"


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require API key auth for tenant-scoped v1 endpoints."""

    _PUBLIC_EXACT: set[tuple[str, str]] = {
        ("GET", "/health"),
        ("POST", "/v1/tenants"),
    }
    _PUBLIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("POST", re.compile(r"^/v1/tenants/[^/]+/api-keys$")),
    )

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if not self._requires_auth(request):
            return await call_next(request)

        db = getattr(request.app.state, "db", None)
        if db is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": {"error": "firestore_unavailable"}},
            )

        api_key = (request.headers.get(_API_KEY_HEADER) or "").strip()
        if not api_key:
            await self._emit_denied(reason="missing_api_key", path=request.url.path)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": {"error": "missing_api_key"}},
            )

        hashed_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        api_key_doc = await _lookup_api_key(db, hashed_key)
        if api_key_doc is None:
            await self._emit_denied(reason="invalid_api_key", path=request.url.path)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": {"error": "invalid_api_key"}},
            )

        request.state.tenant_id = str(api_key_doc["tenant_id"])
        request.state.api_key_id = str(api_key_doc.get("key_id") or "")

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.AUTH_GRANTED,
                tenant_id=request.state.tenant_id,
                actor={"type": "api_key", "id": request.state.api_key_id},
                resource={
                    "kind": "http_request",
                    "path": request.url.path,
                    "method": request.method,
                },
                outcome={"success": True},
            )
        )

        return await call_next(request)

    def _requires_auth(self, request: Request) -> bool:
        path = request.url.path
        method = request.method.upper()

        if not path.startswith("/v1"):
            return False
        if (method, path) in self._PUBLIC_EXACT:
            return False

        for allowed_method, pattern in self._PUBLIC_PATTERNS:
            if method == allowed_method and pattern.match(path):
                return False

        return True

    async def _emit_denied(self, *, reason: str, path: str) -> None:
        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.AUTH_DENIED,
                actor={"type": "api_key"},
                resource={"kind": "http_request", "path": path},
                outcome={"success": False},
                reason=reason,
            )
        )


async def _lookup_api_key(db: Any, hashed_key: str) -> dict[str, Any] | None:
    query = db.collection(_TENANT_KEYS_COLLECTION).where(filter=("key_hash", "==", hashed_key))
    query = query.limit(1)
    docs = await query.get()
    if not docs:
        return None

    doc = docs[0]
    if not doc.exists:
        return None

    data = doc.to_dict()
    if data.get("revoked_at"):
        return None
    return data


def get_request_tenant_id(request: Request) -> str:
    tenant_id = str(getattr(request.state, "tenant_id", "")).strip()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_authenticated_tenant"},
        )
    return tenant_id


def get_request_api_key_id(request: Request) -> str:
    return str(getattr(request.state, "api_key_id", "")).strip()
