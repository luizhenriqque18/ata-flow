"""Migração dos dados legados para var, sem sobrescrever destinos existentes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ataflow.paths import PROJECT_DIR


def ensure_data_layout(home: Path = PROJECT_DIR) -> Path:
    home = Path(home).resolve()
    data = home / "var"
    if data.is_symlink() or not data.resolve().is_relative_to(home):
        raise ValueError("A pasta var precisa permanecer dentro da pasta de dados do AtaFlow.")
    data.mkdir(parents=True, exist_ok=True)
    lock = data / ".migration.lock"
    if lock.exists():
        raise ValueError("Migração em andamento. Feche as instâncias antigas e tente novamente.")
    destinations = {
        "transcricoes": data / "transcricoes",
        "model_preferences.json": data / "model_preferences.json",
        "mcp_preferences.json": data / "mcp_preferences.json",
        "transcriber.log": data / "logs" / "transcriber.log",
    }
    moves = [
        (home / name, target) for name, target in destinations.items() if (home / name).exists()
    ]
    if moves:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("Migração em andamento. Tente novamente após a conclusão.") from exc
        os.close(descriptor)
        completed = []
        try:
            rebased_mcp = _preflight(home, data, moves)
            for old, target in moves:
                target.parent.mkdir(parents=True, exist_ok=True)
                old.rename(target)
                completed.append((old, target))
            if rebased_mcp is not None:
                _write_json(data / "mcp_preferences.json", rebased_mcp)
        except Exception:
            for old, target in reversed(completed):
                target.rename(old)
            raise
        finally:
            lock.unlink()
    for folder in (data / "transcricoes", data / "logs"):
        if folder.is_symlink() or not folder.resolve().is_relative_to(home):
            raise ValueError("As pastas de dados precisam permanecer dentro do AtaFlow.")
        folder.mkdir(exist_ok=True)
    return data


def _preflight(home: Path, data: Path, moves: list[tuple[Path, Path]]) -> dict | None:
    for old, target in moves:
        if (
            old.is_symlink()
            or target.exists()
            or target.is_symlink()
            or not target.resolve().is_relative_to(home)
        ):
            raise ValueError(
                "Dados antigos e novos coexistem ou contêm links. "
                "Nenhum arquivo foi substituído; consulte docs/storage.md."
            )
        if old.name == "transcricoes" and not old.is_dir():
            raise ValueError("A origem transcricoes precisa ser uma pasta.")
        if old.name != "transcricoes" and not old.is_file():
            raise ValueError("A origem das preferências ou do log precisa ser um arquivo.")
    models = home / "model_preferences.json"
    if models.exists():
        from ataflow.summaries.catalog import PreferenceStore

        PreferenceStore(models).load()
    mcp = home / "mcp_preferences.json"
    if not mcp.exists():
        return None
    from ataflow.mcp.settings import MCPSettings

    try:
        raw = json.loads(mcp.read_text(encoding="utf-8"))
        settings = MCPSettings(**raw)
        settings.validate()
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Configuração MCP inválida; migração cancelada e arquivos preservados."
        ) from exc
    original = Path(settings.summaries_dir).expanduser()
    resolved = settings.directory(home)
    legacy_transcripts = home / "transcricoes"
    if resolved.is_relative_to(legacy_transcripts):
        resolved = data / "transcricoes" / resolved.relative_to(legacy_transcripts)
    raw["summaries_dir"] = (
        str(resolved) if original.is_absolute() else os.path.relpath(resolved, data)
    )
    return raw


def _write_json(path: Path, payload: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
