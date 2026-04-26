"""WorkspaceManager: per-run filesystem workspace for Terraform execution."""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any


class WorkspaceManager:
    """Manages an isolated filesystem workspace for a single deployment run.

    Each run gets its own directory under *runs_base_dir* identified by *run_id*.
    The workspace is created on demand and removed by ``cleanup()``.
    """

    def __init__(
        self, run_id: str, runs_base_dir: str = "/tmp/agentcys-runs"
    ) -> None:  # noqa: S108
        self._run_id = run_id
        self._runs_base_dir = Path(runs_base_dir)

    @property
    def workspace_dir(self) -> Path:
        return self._runs_base_dir / self._run_id

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def create(self) -> Path:
        """Create the workspace directory and return its path."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        return self.workspace_dir

    def cleanup(self) -> None:
        """Remove the workspace directory, ignoring any errors."""
        shutil.rmtree(self.workspace_dir, ignore_errors=True)

    # ── File writers ──────────────────────────────────────────────────────

    def write_sa_key(self, key_data: dict[str, Any]) -> Path:
        """Write the service-account JSON key and return its path."""
        sa_key_path = self.workspace_dir / "sa_key.json"
        sa_key_path.write_text(json.dumps(key_data), encoding="utf-8")
        sa_key_path.chmod(0o600)
        return sa_key_path

    def download_module(self, gcs_uri: str, gcs_client: Any) -> Path:
        """Download a GCS tarball and extract it to the workspace.

        *gcs_uri* must be in the form ``gs://bucket/path/to/module.tar.gz``.

        Returns the path to the extracted module directory.
        """
        # Parse gs://bucket/object
        without_scheme = gcs_uri.removeprefix("gs://")
        bucket_name, _, object_path = without_scheme.partition("/")

        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(object_path)

        # Download to a temp file then extract
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        blob.download_to_filename(str(tmp_path))

        module_dir = self.workspace_dir / "module"
        module_dir.mkdir(exist_ok=True)

        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extractall(path=module_dir)  # noqa: S202 — extracted to isolated per-run dir

        tmp_path.unlink(missing_ok=True)
        return module_dir

    def write_tfvars(self, params: dict[str, Any], extra: dict[str, Any]) -> Path:
        """Merge *params* and *extra*, write terraform.tfvars.json, return path."""
        merged = {**params, **extra}
        tfvars_path = self.workspace_dir / "module" / "terraform.tfvars.json"
        tfvars_path.parent.mkdir(parents=True, exist_ok=True)
        tfvars_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return tfvars_path

    def write_backend_tf(self, state_bucket: str, deployment_id: str) -> None:
        """Write backend.tf using the GCS backend for Terraform state storage."""
        prefix = f"terraform/state/{deployment_id}"
        content = f"""\
terraform {{
  backend "gcs" {{
    bucket = "{state_bucket}"
    prefix = "{prefix}"
  }}
}}
"""
        backend_path = self.workspace_dir / "module" / "backend.tf"
        backend_path.parent.mkdir(parents=True, exist_ok=True)
        backend_path.write_text(content, encoding="utf-8")

    def write_provider_tf(self, sa_key_path: Path) -> None:
        """Write provider.tf configuring the google provider."""
        credentials_path = str(sa_key_path.resolve())
        content = f"""\
provider "google" {{
  credentials = "{credentials_path}"
}}
"""
        provider_path = self.workspace_dir / "module" / "provider.tf"
        provider_path.parent.mkdir(parents=True, exist_ok=True)
        provider_path.write_text(content, encoding="utf-8")
