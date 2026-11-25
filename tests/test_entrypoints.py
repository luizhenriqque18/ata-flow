"""Entradas instaladas e adaptadores legados funcionam fora da raiz do projeto."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "arguments",
    [
        ["-m", "ataflow"],
        ["-m", "ataflow.mcp.server"],
        [str(ROOT / "main.py")],
        [str(ROOT / "ataflow_mcp.py")],
    ],
)
def test_module_and_legacy_entries_from_other_directory(tmp_path, arguments):
    result = subprocess.run(
        [sys.executable, *arguments, "--help"],
        cwd=tmp_path,
        env={**os.environ, "ATAFLOW_HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "AtaFlow" in result.stdout


@pytest.mark.parametrize("command", ["ataflow", "ataflow-mcp", "transcriber"])
def test_installed_console_entries(tmp_path, command):
    executable = Path(sys.executable).parent / (command + (".exe" if os.name == "nt" else ""))
    result = subprocess.run(
        [str(executable), "--help"],
        cwd=tmp_path,
        env={**os.environ, "ATAFLOW_HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "AtaFlow" in result.stdout
