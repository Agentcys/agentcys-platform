"""Unit tests for worker.terraform.runner.TerraformRunner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker.terraform.runner import TerraformRunner


@pytest.fixture()
def runner(tmp_path: Path) -> TerraformRunner:
    sa_key = tmp_path / "sa_key.json"
    sa_key.write_text("{}", encoding="utf-8")
    return TerraformRunner(
        working_dir=tmp_path,
        sa_key_path=sa_key,
        tf_binary="terraform",
    )


def _make_result(returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


# ── init ─────────────────────────────────────────────────────────────────────


@patch("subprocess.run")
def test_init_success(mock_run: MagicMock, runner: TerraformRunner) -> None:
    mock_run.return_value = _make_result(0)
    result = runner.init()
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert args[1] == "init"


@patch("subprocess.run")
def test_init_failure(mock_run: MagicMock, runner: TerraformRunner) -> None:
    mock_run.return_value = _make_result(1, stderr=b"Error: something went wrong")
    result = runner.init()
    assert result.returncode == 1


# ── plan ─────────────────────────────────────────────────────────────────────


@patch("subprocess.run")
def test_plan_captures_output(mock_run: MagicMock, runner: TerraformRunner) -> None:
    mock_run.return_value = _make_result(0, stdout=b"Plan: 3 to add")
    result = runner.plan()
    assert result.returncode == 0
    assert result.stdout == b"Plan: 3 to add"
    args = mock_run.call_args[0][0]
    assert "plan" in args
    assert "-out=tfplan" in args


# ── apply ─────────────────────────────────────────────────────────────────────


@patch("subprocess.run")
def test_apply_success(mock_run: MagicMock, runner: TerraformRunner) -> None:
    mock_run.return_value = _make_result(0, stdout=b"Apply complete!")
    result = runner.apply()
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert "apply" in args


# ── destroy ───────────────────────────────────────────────────────────────────


@patch("subprocess.run")
def test_destroy_success(mock_run: MagicMock, runner: TerraformRunner) -> None:
    mock_run.return_value = _make_result(0, stdout=b"Destroy complete!")
    result = runner.destroy()
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert "destroy" in args
    assert "-auto-approve" in args


# ── output_json ───────────────────────────────────────────────────────────────


@patch("subprocess.run")
def test_output_json_parses_correctly(mock_run: MagicMock, runner: TerraformRunner) -> None:
    outputs = {"vpc_id": {"value": "vpc-abc123", "type": "string"}}
    mock_run.return_value = _make_result(0, stdout=json.dumps(outputs).encode())
    result = runner.output_json()
    assert result == outputs


@patch("subprocess.run")
def test_output_json_returns_empty_on_nonzero(mock_run: MagicMock, runner: TerraformRunner) -> None:
    mock_run.return_value = _make_result(1, stderr=b"no state")
    result = runner.output_json()
    assert result == {}
