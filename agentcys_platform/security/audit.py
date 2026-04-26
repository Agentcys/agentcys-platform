"""Unified audit envelope for the Agentcys Platform.

v1: emits structured JSON to stdout (Cloud Logging picks it up).
v2: will route to BigQuery via a listener registered at startup.

Usage::

    from agentcys_platform.security.audit import AuditEvent, AuditSeverity, audit_event_emitter

    await audit_event_emitter.emit(
        AuditEvent(
            event_type=PlatformEvent.DEPLOYMENT_CREATED,
            tenant_id="01HX...",
            actor={"type": "agent", "id": "agent-abc"},
            resource={"kind": "deployment", "id": "dep-123"},
        )
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Event type vocabulary ────────────────────────────────────────────────────


class PlatformEvent(StrEnum):
    # Auth / access
    AUTH_DENIED = "auth.denied"
    AUTH_GRANTED = "auth.granted"

    # Credentials
    CREDENTIAL_UPLOADED = "credential.uploaded"
    CREDENTIAL_ACCESSED = "credential.accessed"
    CREDENTIAL_REVOKED = "credential.revoked"

    # Projects
    PROJECT_LINKED = "project.linked"
    PROJECT_UNLINKED = "project.unlinked"

    # Deployments
    DEPLOYMENT_CREATED = "deployment.created"
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_SUCCEEDED = "deployment.succeeded"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_DESTROYED = "deployment.destroyed"

    # Blueprints
    BLUEPRINT_PUBLISHED = "blueprint.published"

    # State
    STATE_MIRRORED = "state.mirrored"


class AuditSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ── Audit envelope ───────────────────────────────────────────────────────────


@dataclass
class AuditEvent:
    """Platform-wide audit envelope.

    Fields match the structured log schema consumed by Cloud Logging / BigQuery.
    """

    event_type: str
    severity: AuditSeverity = AuditSeverity.INFO
    tenant_id: str = ""
    actor: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    schema_version: int = 1
    event_id: str = field(default_factory=lambda: uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "severity": self.severity.value,
            "tenant_id": self.tenant_id,
            "actor": self.actor,
            "resource": self.resource,
            "outcome": self.outcome,
            "details": self.details,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ── Emitter ──────────────────────────────────────────────────────────────────

AuditListener = Callable[[AuditEvent], Coroutine[Any, Any, None]]


class AuditEmitter:
    """Fan-out audit event bus.

    Listeners are async callables registered at startup.
    v1 always logs to stdout as structured JSON.
    """

    def __init__(self) -> None:
        self._listeners: list[AuditListener] = []
        self._history: list[AuditEvent] = []
        self._max_history = 1000

    def on(self, listener: AuditListener) -> None:
        self._listeners.append(listener)

    def off(self, listener: AuditListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        logger.info("AUDIT %s", json.dumps(event.to_dict(), default=str))

        if self._listeners:
            await asyncio.gather(*(listener(event) for listener in self._listeners))

        return event

    def recent_events(self, limit: int = 50) -> list[AuditEvent]:
        return self._history[-limit:]

    def clear_history(self) -> None:
        self._history.clear()


# ── Module-level singleton ───────────────────────────────────────────────────
audit_event_emitter = AuditEmitter()
