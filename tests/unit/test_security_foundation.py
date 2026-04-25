"""Unit tests for platform/security — audit, tenant_guard, hmac_signer."""

from __future__ import annotations

import time

import pytest

from agentcys_platform.security.audit import (
    AuditEmitter,
    AuditEvent,
    AuditSeverity,
    PlatformEvent,
    audit_event_emitter,
)
from agentcys_platform.security.hmac_signer import sign_payload, verify_signature
from agentcys_platform.security.tenant_guard import (
    actor_tenant_ids,
    can_access_tenant,
    ensure_tenant_access,
    is_platform_wide_actor,
    tenant_filter_for_actor,
)


# ── Audit ────────────────────────────────────────────────────────────────────

class TestAuditEvent:
    def test_to_dict_contains_required_fields(self):
        event = AuditEvent(
            event_type=PlatformEvent.DEPLOYMENT_CREATED,
            tenant_id="tenant-abc",
            actor={"type": "agent", "id": "agent-1"},
            resource={"kind": "deployment", "id": "dep-1"},
        )
        d = event.to_dict()
        assert d["event_type"] == "deployment.created"
        assert d["tenant_id"] == "tenant-abc"
        assert d["actor"] == {"type": "agent", "id": "agent-1"}
        assert d["resource"] == {"kind": "deployment", "id": "dep-1"}
        assert "timestamp" in d
        assert "event_id" in d
        assert d["schema_version"] == 1

    def test_default_severity_is_info(self):
        event = AuditEvent(event_type=PlatformEvent.AUTH_DENIED)
        assert event.severity == AuditSeverity.INFO

    def test_event_id_unique(self):
        e1 = AuditEvent(event_type=PlatformEvent.PROJECT_LINKED)
        e2 = AuditEvent(event_type=PlatformEvent.PROJECT_LINKED)
        assert e1.event_id != e2.event_id

    def test_platform_event_values(self):
        # Spot-check new platform event types are present
        assert PlatformEvent.CREDENTIAL_UPLOADED == "credential.uploaded"
        assert PlatformEvent.DEPLOYMENT_STARTED == "deployment.started"
        assert PlatformEvent.DEPLOYMENT_SUCCEEDED == "deployment.succeeded"
        assert PlatformEvent.DEPLOYMENT_FAILED == "deployment.failed"
        assert PlatformEvent.DEPLOYMENT_DESTROYED == "deployment.destroyed"
        assert PlatformEvent.PROJECT_LINKED == "project.linked"


class TestAuditEmitter:
    async def test_emit_stores_in_history(self):
        emitter = AuditEmitter()
        event = AuditEvent(event_type=PlatformEvent.DEPLOYMENT_CREATED, tenant_id="t1")
        await emitter.emit(event)
        assert len(emitter.recent_events()) == 1
        assert emitter.recent_events()[0].tenant_id == "t1"

    async def test_history_capped_at_max(self):
        emitter = AuditEmitter()
        emitter._max_history = 5
        for i in range(10):
            await emitter.emit(AuditEvent(event_type=PlatformEvent.AUTH_GRANTED))
        assert len(emitter.recent_events()) == 5

    async def test_listener_is_called(self):
        emitter = AuditEmitter()
        received: list[AuditEvent] = []

        async def listener(ev: AuditEvent) -> None:
            received.append(ev)

        emitter.on(listener)
        event = AuditEvent(event_type=PlatformEvent.CREDENTIAL_UPLOADED)
        await emitter.emit(event)
        assert len(received) == 1
        assert received[0].event_type == "credential.uploaded"

    async def test_clear_history(self):
        emitter = AuditEmitter()
        await emitter.emit(AuditEvent(event_type=PlatformEvent.PROJECT_LINKED))
        emitter.clear_history()
        assert emitter.recent_events() == []


# ── Tenant guard ─────────────────────────────────────────────────────────────

class TestTenantGuard:
    def _user(self, tenant_id: str = "", role: str = "member") -> dict:
        return {"tenant_id": tenant_id, "role": role}

    def test_actor_tenant_ids_primary(self):
        user = self._user("t1")
        assert actor_tenant_ids(user) == ["t1"]

    def test_actor_tenant_ids_includes_assigned(self):
        user = {**self._user("t1"), "assigned_tenants": ["t2", "t3"]}
        ids = actor_tenant_ids(user)
        assert "t1" in ids
        assert "t2" in ids
        assert "t3" in ids

    def test_platform_wide_actor(self):
        assert is_platform_wide_actor({"role": "platform_admin"})
        assert is_platform_wide_actor({"role": "support"})
        assert not is_platform_wide_actor(self._user("t1"))

    def test_can_access_own_tenant(self):
        user = self._user("tenant-123")
        assert can_access_tenant(user, "tenant-123")

    def test_cannot_access_other_tenant(self):
        user = self._user("tenant-123")
        assert not can_access_tenant(user, "tenant-456")

    def test_platform_admin_can_access_any_tenant(self):
        user = {"role": "platform_admin"}
        assert can_access_tenant(user, "any-tenant-id")

    def test_ensure_tenant_access_succeeds(self):
        user = self._user("t1")
        result = ensure_tenant_access(user, "t1")
        assert result == "t1"

    def test_ensure_tenant_access_raises_403(self):
        from fastapi import HTTPException

        user = self._user("t1")
        with pytest.raises(HTTPException) as exc_info:
            ensure_tenant_access(user, "t2", resource_label="deployment")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "tenant_scope_denied"

    def test_tenant_filter_single_tenant(self):
        user = self._user("t1")
        f = tenant_filter_for_actor(user)
        assert f == {"tenant_id": "t1"}

    def test_tenant_filter_platform_wide_is_empty(self):
        user = {"role": "platform_admin"}
        assert tenant_filter_for_actor(user) == {}

    def test_tenant_filter_no_scope_raises_403(self):
        from fastapi import HTTPException

        user = {"role": "member", "tenant_id": ""}
        with pytest.raises(HTTPException) as exc_info:
            tenant_filter_for_actor(user)
        assert exc_info.value.status_code == 403


# ── HMAC signer ──────────────────────────────────────────────────────────────

class TestHmacSigner:
    SECRET = "test-secret-value-for-unit-tests-x"

    def test_sign_and_verify_roundtrip(self):
        payload = b'{"deployment_id": "dep-1", "operation": "apply"}'
        sig, ts = sign_payload(payload, self.SECRET)
        assert verify_signature(payload, sig, ts, self.SECRET)

    def test_wrong_secret_fails(self):
        payload = b"hello"
        sig, ts = sign_payload(payload, self.SECRET)
        assert not verify_signature(payload, sig, ts, "wrong-secret")

    def test_tampered_payload_fails(self):
        payload = b"original"
        sig, ts = sign_payload(payload, self.SECRET)
        assert not verify_signature(b"tampered", sig, ts, self.SECRET)

    def test_expired_timestamp_fails(self):
        payload = b"data"
        old_ts = str(int(time.time()) - 400)  # 400s ago > 300s max drift
        import hashlib
        import hmac as hmac_mod

        signed = f"{old_ts}.".encode() + payload
        sig = hmac_mod.new(self.SECRET.encode(), signed, hashlib.sha256).hexdigest()
        assert not verify_signature(payload, sig, old_ts, self.SECRET)

    def test_invalid_timestamp_string_fails(self):
        payload = b"data"
        assert not verify_signature(payload, "badsig", "notanint", self.SECRET)

    def test_different_payloads_produce_different_signatures(self):
        sig1, _ = sign_payload(b"payload-a", self.SECRET)
        sig2, _ = sign_payload(b"payload-b", self.SECRET)
        assert sig1 != sig2

    def test_signature_is_hex_string(self):
        sig, ts = sign_payload(b"test", self.SECRET)
        assert all(c in "0123456789abcdef" for c in sig)
        assert ts.isdigit()
