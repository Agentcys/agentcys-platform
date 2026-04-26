"""Worker-specific settings extending the platform config."""

from __future__ import annotations

from functools import lru_cache

from agentcys_platform.config import Settings


class WorkerSettings(Settings):
    """Extends platform Settings with worker-specific tunables."""

    # HTTP port the FastAPI worker listens on inside Cloud Run
    WORKER_PORT: int = 8080

    # Terraform subprocess timeouts
    TF_TIMEOUT_PLAN_SECONDS: int = 600
    TF_TIMEOUT_APPLY_SECONDS: int = 600
    TF_TIMEOUT_DESTROY_SECONDS: int = 900

    # Path to the terraform binary; override in tests with a fake
    TF_BINARY: str = "terraform"

    # Base directory for per-run working directories
    RUNS_BASE_DIR: str = "/tmp/agentcys-runs"  # noqa: S108


@lru_cache(maxsize=1)
def get_worker_settings() -> WorkerSettings:
    """Return the cached WorkerSettings instance."""
    return WorkerSettings()
