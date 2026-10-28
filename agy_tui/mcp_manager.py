"""Tela de controle do compartilhamento MCP local e pela rede."""

from __future__ import annotations

import secrets

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TextArea,
)

from mcp_settings import MCPSettings, MCPSettingsStore, client_config


class MCPManagerScreen(Screen):
    TITLE = "AtaFlow — Servidor MCP"
    BINDINGS = [("escape", "cancel", "Voltar")]
    DEFAULT_CSS = """
    MCPManagerScreen VerticalScroll { padding: 1 2; }
    MCPManagerScreen Input { margin-bottom: 1; }
    MCPManagerScreen #mcp-client-config { height: 14; margin-bottom: 1; }
    MCPManagerScreen #mcp-actions { height: 3; }
    MCPManagerScreen #mcp-actions Button { margin-right: 1; }
    MCPManagerScreen #mcp-error { color: $error; height: auto; }
    MCPManagerScreen .mcp-token-actions { height: 3; margin-bottom: 1; }
    """

    def __init__(self, store: MCPSettingsStore | None = None) -> None:
        super().__init__()
        self.store = store or MCPSettingsStore()
        self.settings = self.store.load()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(
                "Compartilhe resumos por MCP local (stdio) ou pela rede (Streamable HTTP). "
                "Somente arquivos *-resumo.md da pasta escolhida ficam disponíveis."
            )
            yield Label("Permitir acesso aos resumos (aplicado ao salvar)")
            yield Switch(self.settings.enabled, id="mcp-enabled")
            yield Label("Pasta de resumos (relativa à configuração ou absoluta)")
            yield Input(self.settings.summaries_dir, id="mcp-directory")
            yield Label("Resultados por página (1–100)")
            yield Input(str(self.settings.max_results), id="mcp-results", type="integer")
            yield Label("Caracteres por leitura e busca (1.000–100.000)")
            yield Input(str(self.settings.max_chars), id="mcp-chars", type="integer")
            yield Static("", id="mcp-network-status")
            with Collapsible(title="Acesso pela rede (HTTP)", collapsed=True):
                yield Label("Iniciar servidor HTTP ao salvar e ao abrir o AtaFlow")
                yield Switch(self.settings.network_enabled, id="mcp-network-enabled")
                yield Label("IP de escuta (0.0.0.0 para todas as interfaces IPv4)")
                yield Input(self.settings.http_host, id="mcp-host")
                yield Label("Porta HTTP")
                yield Input(str(self.settings.http_port), type="integer", id="mcp-port")
                yield Label("IP ou DNS desta máquina que o outro computador usará")
                yield Input(self.settings.http_public_host, id="mcp-public-host")
                yield Label("Token de acesso (obrigatório na rede)")
                yield Input(self.settings.http_token, password=True, id="mcp-token")
                with Horizontal(classes="mcp-token-actions"):
                    yield Button("Gerar novo token", id="mcp-generate-token")
                    yield Button("Copiar token", id="mcp-copy-token")
                yield Static(
                    "Use HTTP somente em rede confiável ou VPN. Para redes não confiáveis, "
                    "use um proxy HTTPS. O servidor funciona enquanto o AtaFlow estiver aberto; "
                    "docs/mcp.md explica como executá-lo separadamente."
                )
            yield Static("", id="mcp-error")
            yield Label("Conexão: valores salvos (salve e reabra após alterar a rede)")
            yield Select(
                [
                    ("Local — Codex (config.toml)", "codex"),
                    ("Local — outros clientes (JSON)", "json"),
                    ("Rede — Codex (config.toml)", "http-codex"),
                    ("Rede — outros clientes (JSON)", "http-json"),
                ],
                value="codex",
                allow_blank=False,
                id="mcp-format",
            )
            yield TextArea(
                client_config(self.store, "codex"),
                read_only=True,
                id="mcp-client-config",
            )
            yield Static(
                "Salvar atualiza o acesso nas próximas chamadas, inclusive de clientes conectados. "
                "Desativar bloqueia novas leituras; textos já enviados continuam no chat. "
                "Consulte docs/mcp.md para configurar o Codex e exemplos de uso."
            )
            with Horizontal(id="mcp-actions"):
                yield Button("Salvar", id="mcp-save", variant="primary")
                yield Button("Copiar conexão", id="mcp-copy")
                yield Button("Cancelar", id="mcp-cancel")
        yield Footer()

    @on(Button.Pressed, "#mcp-save")
    async def save_settings(self) -> None:
        try:
            settings = MCPSettings(
                enabled=self.query_one("#mcp-enabled", Switch).value,
                summaries_dir=self.query_one("#mcp-directory", Input).value.strip(),
                max_results=int(self.query_one("#mcp-results", Input).value),
                max_chars=int(self.query_one("#mcp-chars", Input).value),
                network_enabled=self.query_one("#mcp-network-enabled", Switch).value,
                http_host=self.query_one("#mcp-host", Input).value.strip(),
                http_port=int(self.query_one("#mcp-port", Input).value),
                http_public_host=self.query_one("#mcp-public-host", Input).value.strip(),
                http_token=self.query_one("#mcp-token", Input).value.strip(),
            )
            self.store.save(settings)
        except (ValueError, OSError) as exc:
            self.query_one("#mcp-error", Static).update(f"Não foi possível salvar: {exc}")
            return
        service = getattr(self.app, "mcp_http_service", None)
        if service is not None:
            try:
                await service.apply()
            except (ValueError, OSError) as exc:
                self.query_one("#mcp-error", Static).update(
                    f"Configuração salva, mas o HTTP não iniciou: {exc}. "
                    "Verifique IP/porta ou desative o acesso pela rede e salve."
                )
                self.refresh_network_status()
                return
        self.app.notify("Acesso MCP ativado." if settings.enabled else "Acesso MCP desativado.")
        self.dismiss(None)

    def on_mount(self) -> None:
        self.refresh_network_status()
        self.set_interval(2, self.refresh_network_status)

    def refresh_network_status(self) -> None:
        service = getattr(self.app, "mcp_http_service", None)
        running = service is not None and service.running
        status = "HTTP ativo" if running else "HTTP parado"
        if running:
            try:
                status += f" — {self.store.load().http_url()}"
            except (ValueError, OSError):
                status = "Configuração inválida; acesso bloqueado"
        self.query_one("#mcp-network-status", Static).update(status)

    @on(Button.Pressed, "#mcp-generate-token")
    def generate_token(self) -> None:
        self.query_one("#mcp-token", Input).value = secrets.token_urlsafe(32)
        self.app.notify("Novo token gerado. Salve para aplicá-lo.")

    @on(Button.Pressed, "#mcp-copy-token")
    def copy_token(self) -> None:
        self.app.copy_to_clipboard(self.query_one("#mcp-token", Input).value)
        self.app.notify("Token copiado. Configure-o no outro computador; salve para aplicá-lo.")

    @on(Button.Pressed, "#mcp-copy")
    def copy_connection(self) -> None:
        self.app.copy_to_clipboard(self.query_one("#mcp-client-config", TextArea).text)
        self.app.notify("Configuração de conexão copiada.")

    @on(Select.Changed, "#mcp-format")
    def change_format(self, event: Select.Changed) -> None:
        self.query_one("#mcp-client-config", TextArea).load_text(
            client_config(self.store, str(event.value)),
        )

    @on(Button.Pressed, "#mcp-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
