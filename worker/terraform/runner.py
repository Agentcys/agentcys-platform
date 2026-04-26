"""TerraformRunner: thin subprocess wrapper around the terraform CLI."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TerraformRunner:
    """Runs terraform subprocesses inside a pre-prepared workspace directory.

    All commands inherit a sanitised environment that sets essential Terraform
    automation flags and injects the Google credentials path.
    """

    def __init__(
        self,
        working_dir: Path,
        sa_key_path: Path,
        tf_binary: str = "terraform",
    ) -> None:
        self._working_dir = working_dir
        self._tf_binary = tf_binary
        self._env: dict[str, str] = {
            **os.environ,
            "GOOGLE_APPLICATION_CREDENTIALS": str(sa_key_path),
            "TF_IN_AUTOMATION": "1",
            "TF_INPUT": "0",
            "TF_CLI_ARGS_init": "-no-color",
            "TF_CLI_ARGS_plan": "-no-color",
            "TF_CLI_ARGS_apply": "-no-color",
            "TF_CLI_ARGS_destroy": "-no-color",
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _run(
        self,
        args: list[str],
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[bytes]:
        cmd = [self._tf_binary, *args]
        logger.info("Running: %s (cwd=%s)", " ".join(cmd), self._working_dir)
        return subprocess.run(
            cmd,
            cwd=self._working_dir,
            env=self._env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )

    # ── Public commands ───────────────────────────────────────────────────

    def init(self, timeout: int = 300) -> subprocess.CompletedProcess[bytes]:
        """Run ``terraform init``."""
        return self._run(["init"], timeout)

    def plan(
        self,
        out_file: str = "tfplan",
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[bytes]:
        """Run ``terraform plan -out=<out_file>``."""
        return self._run(["plan", f"-out={out_file}"], timeout)

    def apply(
        self,
        plan_file: str = "tfplan",
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[bytes]:
        """Run ``terraform apply <plan_file>``."""
        return self._run(["apply", plan_file], timeout)

    def destroy(self, timeout: int = 900) -> subprocess.CompletedProcess[bytes]:
        """Run ``terraform destroy -auto-approve``."""
        return self._run(["destroy", "-auto-approve"], timeout)

    def output_json(self, timeout: int = 60) -> dict[str, Any]:
        """Run ``terraform output -json`` and return the parsed dict."""
        result = self._run(["output", "-json"], timeout)
        if result.returncode != 0:
            logger.warning(
                "terraform output -json returned %d: %s",
                result.returncode,
                result.stderr.decode(errors="replace"),
            )
            return {}
        try:
            return json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            logger.warning("Failed to parse terraform output JSON")
            return {}
