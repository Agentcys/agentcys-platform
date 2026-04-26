"""Unit tests for worker.terraform.state_mirror.mirror_state."""

from __future__ import annotations

from unittest.mock import MagicMock

from worker.terraform.state_mirror import mirror_state


def _make_gcs_client(state_bytes: bytes = b'{"version":4}') -> MagicMock:
    src_blob = MagicMock()
    src_blob.download_as_bytes.return_value = state_bytes

    dst_blob = MagicMock()

    src_bucket = MagicMock()
    src_bucket.blob.return_value = src_blob

    dst_bucket = MagicMock()
    dst_bucket.blob.return_value = dst_blob

    client = MagicMock()
    client.bucket.side_effect = lambda name: src_bucket if name == "src-bucket" else dst_bucket
    return client, src_blob, dst_blob


def test_mirror_state_copies_blob() -> None:
    gcs_client, src_blob, dst_blob = _make_gcs_client(state_bytes=b'{"version":4}')

    mirror_state(
        state_bucket="src-bucket",
        deployment_id="dep-001",
        tenant_id="tenant-001",
        project_id="proj-001",
        mirror_bucket="mirror-bucket",
        gcs_client=gcs_client,
    )

    src_blob.download_as_bytes.assert_called_once()
    dst_blob.upload_from_string.assert_called_once_with(
        b'{"version":4}', content_type="application/json"
    )


def test_mirror_state_logs_warning_on_error_and_does_not_raise() -> None:
    """If GCS raises, mirror_state must not re-raise."""
    gcs_client = MagicMock()
    gcs_client.bucket.side_effect = Exception("GCS unavailable")

    # Should not raise
    mirror_state(
        state_bucket="src-bucket",
        deployment_id="dep-001",
        tenant_id="tenant-001",
        project_id="proj-001",
        mirror_bucket="mirror-bucket",
        gcs_client=gcs_client,
    )
