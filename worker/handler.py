"""Cloud Tasks worker handler — stub (see runner.py for full implementation)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def execute_run(
    run_id: str,
    deployment_id: str,
    firestore_client: Any,
    gcs_client: Any,
    secrets_client: Any,
) -> None:
    """Orchestrate a Terraform deployment run end-to-end.

    Full implementation in commit 2; this stub prevents import errors.
    """
    raise NotImplementedError("execute_run not yet implemented — see commit 2")
