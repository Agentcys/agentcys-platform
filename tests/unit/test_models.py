"""Unit tests for Pydantic models — serialization round-trips and validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentcys_platform.models.blueprint import Blueprint, BlueprintVersion
from agentcys_platform.models.credential import CustomerCredential
from agentcys_platform.models.deployment import Deployment
from agentcys_platform.models.project import CustomerProject
from agentcys_platform.models.run import DeploymentRun
from agentcys_platform.models.tenant import Tenant

NOW = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)


# ── Tenant ───────────────────────────────────────────────────────────────────


class TestTenant:
    def _make(self, **kwargs) -> Tenant:
        return Tenant(
            tenant_id="t-01",
            name="Acme Corp",
            created_at=NOW,
            **kwargs,
        )

    def test_default_plan_is_free(self):
        assert self._make().plan == "free"

    def test_to_firestore_roundtrip(self):
        t = self._make(plan="pro")
        doc = t.to_firestore()
        assert doc["tenant_id"] == "t-01"
        assert doc["plan"] == "pro"
        t2 = Tenant.from_firestore(doc)
        assert t2.tenant_id == t.tenant_id
        assert t2.plan == t.plan

    def test_invalid_plan_raises(self):
        with pytest.raises(Exception):  # noqa: B017
            self._make(plan="enterprise_plus")

    def test_created_at_preserved(self):
        doc = self._make().to_firestore()
        t2 = Tenant.from_firestore(doc)
        assert t2.created_at == NOW


# ── CustomerProject ───────────────────────────────────────────────────────────


class TestCustomerProject:
    def _make(self, **kwargs) -> CustomerProject:
        return CustomerProject(
            project_id="proj-01",
            gcp_project_id="acme-prod-1234",
            tenant_id="t-01",
            default_region="us-central1",
            credential_id="cred-01",
            state_bucket="acme-tf-state",
            created_at=NOW,
            **kwargs,
        )

    def test_default_status_is_linked(self):
        assert self._make().status == "linked"

    def test_roundtrip(self):
        p = self._make(status="revoked")
        doc = p.to_firestore()
        p2 = CustomerProject.from_firestore(doc)
        assert p2.project_id == p.project_id
        assert p2.status == "revoked"
        assert p2.gcp_project_id == "acme-prod-1234"


# ── CustomerCredential ────────────────────────────────────────────────────────


class TestCustomerCredential:
    def _make(self, **kwargs) -> CustomerCredential:
        return CustomerCredential(
            credential_id="cred-01",
            tenant_id="t-01",
            kind="sa_key",
            secret_manager_uri="projects/our-proj/secrets/cred-01/versions/latest",  # noqa: S106
            sa_email="svc@acme.iam.gserviceaccount.com",
            created_at=NOW,
            **kwargs,
        )

    def test_optional_dates_default_none(self):
        c = self._make()
        assert c.last_used_at is None
        assert c.revoked_at is None

    def test_roundtrip_with_dates(self):
        c = self._make(last_used_at=NOW, revoked_at=NOW)
        doc = c.to_firestore()
        c2 = CustomerCredential.from_firestore(doc)
        assert c2.last_used_at == NOW
        assert c2.revoked_at == NOW

    def test_roundtrip_without_optional_dates(self):
        doc = self._make().to_firestore()
        c2 = CustomerCredential.from_firestore(doc)
        assert c2.last_used_at is None
        assert c2.revoked_at is None


# ── Blueprint ─────────────────────────────────────────────────────────────────


class TestBlueprint:
    def test_roundtrip(self):
        bp = Blueprint(
            blueprint_id="cloud-run-service",
            name="Cloud Run Service",
            description="Deploys a Cloud Run service",
            latest_version="1.0.0",
        )
        doc = bp.to_firestore()
        bp2 = Blueprint.from_firestore(doc)
        assert bp2.blueprint_id == bp.blueprint_id
        assert bp2.latest_version == "1.0.0"


class TestBlueprintVersion:
    def test_immutable_default_true(self):
        bv = BlueprintVersion(
            blueprint_id="cloud-run-service",
            version="1.0.0",
            tf_module_uri="gs://blueprints/cloud-run-service/1.0.0.tar.gz",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            published_at=NOW,
        )
        assert bv.immutable is True

    def test_roundtrip(self):
        bv = BlueprintVersion(
            blueprint_id="cloud-run-service",
            version="1.0.0",
            tf_module_uri="gs://blueprints/cloud-run-service/1.0.0.tar.gz",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            published_at=NOW,
        )
        doc = bv.to_firestore()
        bv2 = BlueprintVersion.from_firestore(doc)
        assert bv2.version == "1.0.0"
        assert bv2.published_at == NOW


# ── Deployment ────────────────────────────────────────────────────────────────


class TestDeployment:
    def _make(self, **kwargs) -> Deployment:
        return Deployment(
            deployment_id="dep-01",
            tenant_id="t-01",
            project_id="proj-01",
            blueprint_id="cloud-run-service",
            blueprint_version="1.0.0",
            name="my-api",
            params={"image": "gcr.io/acme/api:latest"},
            created_at=NOW,
            updated_at=NOW,
            **kwargs,
        )

    def test_default_status_is_pending(self):
        assert self._make().status == "pending"

    def test_outputs_default_none(self):
        assert self._make().outputs is None

    def test_roundtrip(self):
        d = self._make(status="applied", outputs={"url": "https://api.run.app"})
        doc = d.to_firestore()
        d2 = Deployment.from_firestore(doc)
        assert d2.status == "applied"
        assert d2.outputs == {"url": "https://api.run.app"}
        assert d2.params == {"image": "gcr.io/acme/api:latest"}

    def test_invalid_status_raises(self):
        with pytest.raises(Exception):  # noqa: B017
            self._make(status="unknown-status")


# ── DeploymentRun ─────────────────────────────────────────────────────────────


class TestDeploymentRun:
    def _make(self, **kwargs) -> DeploymentRun:
        return DeploymentRun(
            run_id="run-01",
            deployment_id="dep-01",
            operation="apply",
            actor={"type": "agent", "id": "agent-xyz"},
            **kwargs,
        )

    def test_default_status_queued(self):
        assert self._make().status == "queued"

    def test_optional_fields_default_none(self):
        r = self._make()
        assert r.tf_plan_uri is None
        assert r.started_at is None
        assert r.finished_at is None
        assert r.error is None

    def test_roundtrip_with_timestamps(self):
        r = self._make(started_at=NOW, finished_at=NOW, status="succeeded")
        doc = r.to_firestore()
        r2 = DeploymentRun.from_firestore(doc)
        assert r2.status == "succeeded"
        assert r2.started_at == NOW
        assert r2.finished_at == NOW

    def test_actor_shape_preserved(self):
        doc = self._make().to_firestore()
        r2 = DeploymentRun.from_firestore(doc)
        assert r2.actor == {"type": "agent", "id": "agent-xyz"}
