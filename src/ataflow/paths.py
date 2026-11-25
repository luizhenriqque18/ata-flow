"""Localização estável dos arquivos locais, independente do diretório do terminal."""

from __future__ import annotations

import os
from pathlib import Path


def application_home() -> Path:
    if configured := os.environ.get("ATAFLOW_HOME"):
        return Path(configured).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").is_file() and (checkout / "src" / "ataflow").is_dir():
        return checkout
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "AtaFlow"


PROJECT_DIR = application_home()
