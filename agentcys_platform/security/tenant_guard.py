"""Tenant scoping helpers — enforce cross-tenant isolation.

Every authenticated request carries a verified ``tenant_id``.  These helpers
assert that the caller is allowed to access the requested resource, raising a
403 with an AUTH_DENIED audit event on violations.

Usage::

    from agentcys_platform.security.tenant_guard import ensure_tenant_access

    # Raises 403 if the caller cannot access `target_tenant_id`
    ensure_tenant_access(current_user, target_tenant_id)
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

# Roles that span all tenants (platform operators).
_PLATFORM_WIDE_ROLES = {"platform_admin", "platform_ops", "support"}


# ── Actor helpers ────────────────────────────────────────────────────────────


def get_actor_role(user: dict[str, Any]) -> str:
    return str(user.get("role") or "viewer").strip()


def actor_tenant_ids(user: dict[str, Any]) -> list[str]:
    """Return all tenant IDs the actor is allowed to access."""
    ids: list[str] = []
    primary = str(user.get("tenant_id") or "").strip()
    if primary:
        ids.append(primary)

    for extra in user.get("assigned_tenants", []) or []:
        normalized = str(extra or "").strip()
        if normalized and normalized not in ids:
            ids.append(normalized)

    return ids


def is_platform_wide_actor(user: dict[str, Any]) -> bool:
    return get_actor_role(user) in _PLATFORM_WIDE_ROLES


def can_access_tenant(user: dict[str, Any], tenant_id: str) -> bool:
    normalized = str(tenant_id or "").strip()
    if not normalized:
        return False
    if is_platform_wide_actor(user):
        return True
    return normalized in actor_tenant_ids(user)


# ── Guard ────────────────────────────────────────────────────────────────────


def ensure_tenant_access(
    user: dict[str, Any],
    tenant_id: str,
    *,
    resource_label: str = "resource",
) -> str:
    """Assert the actor may access *tenant_id*.

    Returns the normalised tenant_id on success.
    Raises HTTP 403 on violation.

    The caller is responsible for emitting an AUTH_DENIED audit event when
    appropriate (typically done in the route layer).
    """
    normalized = str(tenant_id or "").strip()
    if can_access_tenant(user, normalized):
        return normalized

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "tenant_scope_denied",
            "detail": f"Actor cannot access {resource_label} in tenant '{normalized}'",
            "tenant_id": normalized,
        },
    )


def tenant_filter_for_actor(
    user: dict[str, Any],
    *,
    tenant_field: str = "tenant_id",
) -> dict[str, Any]:
    """Return a Firestore-compatible filter dict scoped to the actor's tenants.

    Platform-wide roles get an empty filter (no restriction).
    Raises HTTP 403 if the actor has no tenant scope at all.
    """
    if is_platform_wide_actor(user):
        return {}

    ids = actor_tenant_ids(user)
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "tenant_scope_missing",
                "detail": "Actor has no tenant scope assigned",
            },
        )

    if len(ids) == 1:
        return {tenant_field: ids[0]}
    return {tenant_field: {"__in": ids}}
