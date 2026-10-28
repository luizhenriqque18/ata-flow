"""Preferências locais do MCP, compartilhadas pela TUI e pelo servidor."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_DIR / "mcp_preferences.json"


@dataclass(frozen=True)
class MCPSettings:
    enabled: bool = False
    summaries_dir: str = "transcricoes"
    max_results: int = 20
    max_chars: int = 20000
    network_enabled: bool = False
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    http_public_host: str = "127.0.0.1"
    http_token: str = field(default="", repr=False)

    def validate(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("Ativação deve ser verdadeira ou falsa.")
        if not isinstance(self.summaries_dir, str) or not self.summaries_dir.strip():
            raise ValueError("Informe a pasta de resumos.")
        if type(self.max_results) is not int or not 1 <= self.max_results <= 100:
            raise ValueError("Limite de resultados: entre 1 e 100.")
        if type(self.max_chars) is not int or not 1000 <= self.max_chars <= 100000:
            raise ValueError("Limite de caracteres: entre 1.000 e 100.000.")
        if type(self.network_enabled) is not bool:
            raise ValueError("Ativação de rede deve ser verdadeira ou falsa.")
        if not isinstance(self.http_host, str):
            raise ValueError("Endereço de escuta deve ser um IP em texto.")
        try:
            ipaddress.ip_address(self.http_host)
        except (ValueError, TypeError) as exc:
            raise ValueError("Endereço de escuta deve ser um IP, como 0.0.0.0.") from exc
        if type(self.http_port) is not int or not 1 <= self.http_port <= 65535:
            raise ValueError("Porta HTTP: entre 1 e 65535.")
        if not isinstance(self.http_public_host, str) or not re.fullmatch(
            r"[A-Za-z0-9_.:\-]+",
            self.http_public_host,
        ):
            raise ValueError("Informe o IP ou nome DNS que a outra máquina usará, sem http://.")
        if self.http_public_host in {"0.0.0.0", "::"}:
            raise ValueError("O endereço do cliente deve ser o IP real da máquina, não 0.0.0.0.")
        if ":" in self.http_public_host:
            try:
                ipaddress.IPv6Address(self.http_public_host)
            except ValueError as exc:
                raise ValueError("Endereço IPv6 do cliente inválido.") from exc
        if not isinstance(self.http_token, str) or (
            self.http_token
            and not re.fullmatch(
                r"[A-Za-z0-9_-]{32,256}",
                self.http_token,
            )
        ):
            raise ValueError("Token deve ter 32–256 caracteres: letras, números, _ ou -.")
        if self.network_enabled and not self.http_token:
            raise ValueError("Gere ou informe um token antes de ativar o acesso pela rede.")

    def http_url(self) -> str:
        host = self.http_public_host
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{self.http_port}/mcp"

    def directory(self, base: Path = PROJECT_DIR) -> Path:
        path = Path(self.summaries_dir).expanduser()
        return (path if path.is_absolute() else base / path).resolve()


class MCPSettingsStore:
    def __init__(self, path: Path = SETTINGS_PATH) -> None:
        self.path = Path(path).resolve()

    def load(self) -> MCPSettings:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return MCPSettings()
        try:
            settings = MCPSettings(**json.loads(raw))
            settings.validate()
            return settings
        except (TypeError, ValueError) as exc:
            raise ValueError("Configuração MCP inválida; acesso bloqueado.") from exc

    def save(self, settings: MCPSettings) -> None:
        settings.validate()
        directory = settings.directory(self.path.parent)
        if not directory.is_dir():
            raise ValueError("A pasta de resumos precisa existir.")
        name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                delete=False,
            ) as stream:
                name = stream.name
                json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(name, self.path)
        finally:
            if name and Path(name).exists():
                Path(name).unlink()


def client_config(store: MCPSettingsStore, format: str = "json") -> str:
    """Conexão local ou HTTP em TOML/JSON; não inclui o token secreto."""
    if format in {"http-codex", "http-json"}:
        url = store.load().http_url()
        if format == "http-codex":
            return (
                "[mcp_servers.ataflow]\n"
                f"url = {json.dumps(url)}\n"
                'bearer_token_env_var = "ATAFLOW_MCP_TOKEN"\n'
            )
        return json.dumps(
            {
                "mcpServers": {
                    "ataflow": {
                        "url": url,
                        "headers": {"Authorization": "Bearer <TOKEN_CONFIGURADO_NO_ATAFLOW>"},
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        )
    entry = {
        "command": sys.executable,
        "args": [str(PROJECT_DIR / "ataflow_mcp.py"), "--config", str(store.path)],
    }
    if format == "codex":
        return (
            "[mcp_servers.ataflow]\n"
            f"command = {json.dumps(entry['command'])}\n"
            f"args = {json.dumps(entry['args'])}\n"
        )
    return json.dumps({"mcpServers": {"ataflow": entry}}, ensure_ascii=False, indent=2)
