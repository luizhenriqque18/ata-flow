"""
Telas (Screens) reutilizaveis da plataforma agy_tui.

Telas disponiveis:
  - DeviceSetupScreen    : selecao interativa de microfone e loopback de audio
  - ModelSelectionModal  : modal para escolha de Provider e Modelo LLM
  - DashboardScreen      : tela inicial com historico e acoes
  - SummaryViewerScreen  : visualizacao de resumo em Markdown
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    MarkdownViewer,
    Static,
)

from agy_tui.model_manager import ModelSelectionModal as ModelSelectionModal

# ======================================================================
# Dataclass compartilhado
# ======================================================================


@dataclass
class DeviceSelection:
    """Resultado da selecao de dispositivos pelo usuario."""

    mic_index: int | None
    mic_name: str
    sys_index: int | None
    sys_name: str


# ======================================================================
# Tela de selecao de dispositivos de audio
# ======================================================================


class DeviceSetupScreen(Screen[DeviceSelection | None]):
    """
    Tela interativa para selecao de microfone e loopback de audio.
    Retorna DeviceSelection ao confirmar, ou None ao cancelar.
    """

    TITLE = "Configuracao de Dispositivos"

    DEFAULT_CSS = """
    DeviceSetupScreen {
        align: center middle;
    }

    #setup-container {
        width: 90;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }

    #setup-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #setup-hint {
        text-align: center;
        color: $text-disabled;
        margin-bottom: 1;
    }

    .device-section {
        height: auto;
        margin-bottom: 1;
    }

    .section-label {
        text-style: bold;
        color: $accent;
        padding: 0 0 0 1;
    }

    DataTable {
        height: 7;
        border: round $primary 50%;
    }

    DataTable:focus {
        border: round $primary;
    }

    #selected-info {
        height: 3;
        border: round $success 50%;
        padding: 0 1;
        margin-top: 1;
    }

    #btn-row {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
        min-width: 20;
    }

    Button#btn-start {
        background: $success 80%;
    }

    Button#btn-start:hover,
    Button#btn-start:focus {
        background: $success;
        text-style: bold;
    }

    Button#btn-start:disabled {
        background: $panel;
        color: $text-disabled;
    }
    """

    BINDINGS = [
        Binding("tab", "focus_next", "Focar", show=False),
        Binding("ctrl+s", "start", "Iniciar (Atalho)", show=True),
        Binding("escape", "cancel", "Voltar", show=True),
    ]

    def __init__(self, devices: dict[str, list[dict]]) -> None:
        super().__init__()
        self._devices = devices
        self._selected_mic: dict | None = None
        self._selected_sys: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="setup-container"):
            yield Static("[bold]AtaFlow[/bold] — Selecao de Dispositivos", id="setup-title")
            yield Static(
                "Navegue com as [bold]Setas[/] e aperte [bold]Enter[/] "
                "para confirmar cada dispositivo.",
                id="setup-hint",
            )
            with Vertical(classes="device-section"):
                yield Label("1. Microfone (sua voz):", classes="section-label")
                yield DataTable(id="mic-table", cursor_type="row", zebra_stripes=True)
            with Vertical(classes="device-section"):
                yield Label(
                    "2. Audio do Sistema (loopback — voz dos outros):", classes="section-label"
                )
                yield DataTable(id="sys-table", cursor_type="row", zebra_stripes=True)
            yield Static("", id="selected-info")
            with Horizontal(id="btn-row"):
                yield Button("Iniciar Gravacao", id="btn-start", disabled=True, variant="success")
                yield Button("Voltar", id="btn-cancel", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        mic_table = self.query_one("#mic-table", DataTable)
        mic_table.add_columns("Idx", "Nome", "Canais")
        for dev in self._devices.get("mics", []):
            mic_table.add_row(
                str(dev["index"]),
                dev["name"],
                str(dev["maxInputChannels"]),
                key=str(dev["index"]),
            )

        sys_table = self.query_one("#sys-table", DataTable)
        sys_table.add_columns("Idx", "Nome", "Canais")
        for dev in self._devices.get("loopbacks", []):
            sys_table.add_row(
                str(dev["index"]),
                dev["name"],
                str(dev["maxInputChannels"]),
                key=str(dev["index"]),
            )

        mic_table.focus()
        self._update_info()

    @on(DataTable.RowSelected, "#mic-table")
    def on_mic_selected(self, event: DataTable.RowSelected) -> None:
        mics = self._devices.get("mics", [])
        if event.cursor_row < len(mics):
            self._selected_mic = mics[event.cursor_row]
            self._update_info()
            self.query_one("#sys-table", DataTable).focus()

    @on(DataTable.RowSelected, "#sys-table")
    def on_sys_selected(self, event: DataTable.RowSelected) -> None:
        loopbacks = self._devices.get("loopbacks", [])
        if event.cursor_row < len(loopbacks):
            self._selected_sys = loopbacks[event.cursor_row]
            self._update_info()
            if self._selected_mic and self._selected_sys:
                self.query_one("#btn-start", Button).focus()

    def _update_info(self) -> None:
        mic = self._selected_mic
        sys_ = self._selected_sys
        mic_str = f"[green]✓[/] {mic['name']}" if mic else "[dim]Pendente...[/]"
        sys_str = f"[green]✓[/] {sys_['name']}" if sys_ else "[dim]Pendente...[/]"
        self.query_one("#selected-info", Static).update(f"Mic: {mic_str}   |   Sistema: {sys_str}")
        self.query_one("#btn-start", Button).disabled = not (mic and sys_)

    @on(Button.Pressed, "#btn-start")
    def on_start(self) -> None:
        if self._selected_mic and self._selected_sys:
            self.dismiss(
                DeviceSelection(
                    mic_index=self._selected_mic["index"],
                    mic_name=self._selected_mic["name"],
                    sys_index=self._selected_sys["index"],
                    sys_name=self._selected_sys["name"],
                )
            )

    def action_start(self) -> None:
        self.on_start()

    def action_cancel(self) -> None:
        """Volta ao Dashboard sem selecionar dispositivos."""
        self.dismiss(None)

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)


# ======================================================================
# Dashboard Principal
# ======================================================================


class DashboardScreen(Screen):
    """
    Tela inicial do AtaFlow.

    Painel esquerdo: botoes de acao (Nova Gravacao, Atualizar Lista).
    Painel direito:  tabela com historico de transcricoes.
      - Linha pendente (sem resumo) -> dispara geracao de resumo.
      - Linha resumida              -> abre o visualizador de Markdown.
    A lista e atualizada automaticamente ao retornar de qualquer fluxo.
    """

    TITLE = "AtaFlow 2.0"
    SUB_TITLE = "Dashboard"

    DEFAULT_CSS = """
    DashboardScreen {
        layout: vertical;
    }

    #dashboard-layout {
        width: 100%;
        height: 1fr;
    }

    #left-pane {
        width: 30;
        height: 100%;
        border-right: solid $primary;
        padding: 1 2;
    }

    #left-pane-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #left-pane Button {
        width: 100%;
        margin-bottom: 1;
    }

    #right-pane {
        width: 1fr;
        height: 100%;
        padding: 1;
    }

    #right-pane-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #history-table {
        height: 1fr;
        border: round $primary 50%;
    }

    #history-table:focus {
        border: round $primary;
    }

    #empty-msg {
        text-align: center;
        color: $text-disabled;
        margin-top: 3;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "start_new", "Nova Gravacao", show=True),
        Binding("r", "refresh_list", "Atualizar", show=True),
        Binding("ctrl+c", "app.quit", "Sair", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="dashboard-layout"):
            with Vertical(id="left-pane"):
                yield Static("Acoes", id="left-pane-title")
                yield Button("Nova Gravacao", id="btn-new", variant="success")
                yield Button("Atualizar Lista", id="btn-refresh")
                yield Button("Gerenciar modelos", id="btn-models")
                yield Button("Servidor MCP", id="btn-mcp")
            with Vertical(id="right-pane"):
                yield Static("[bold]Historico de Transcricoes[/bold]", id="right-pane-title")
                yield Static("Nenhuma transcricao encontrada.", id="empty-msg")
                yield DataTable(id="history-table", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Status", "Data/Hora", "Arquivo")
        self.refresh_history()

    def refresh_history(self) -> None:
        """Recarrega a lista de transcricoes a partir do disco."""
        table = self.query_one("#history-table", DataTable)
        empty_msg = self.query_one("#empty-msg", Static)
        table.clear()

        out_dir = Path("transcricoes")
        txt_files = sorted(out_dir.glob("*.txt"), reverse=True) if out_dir.exists() else []

        if not txt_files:
            empty_msg.display = True
            table.display = False
            return

        empty_msg.display = False
        table.display = True

        for txt in txt_files:
            summary = txt.with_name(txt.stem + "-resumo.md")
            pending = not summary.exists()
            status = "⚠️  Pendente" if pending else "✅ Resumido"
            dt_str = txt.stem.replace("transcricao_", "")
            table.add_row(status, dt_str, txt.name, key=str(txt))

    def action_refresh_list(self) -> None:
        self.refresh_history()
        self.app.notify("Lista atualizada.")

    def action_start_new(self) -> None:
        self.app.post_message(self.app.StartNewRecording())

    @on(Button.Pressed, "#btn-refresh")
    def on_btn_refresh(self) -> None:
        self.refresh_history()
        self.app.notify("Lista atualizada.")

    @on(Button.Pressed, "#btn-models")
    def on_btn_models(self) -> None:
        self.app.post_message(self.app.ManageModels())

    @on(Button.Pressed, "#btn-new")
    def on_btn_new(self) -> None:
        self.app.post_message(self.app.StartNewRecording())

    @on(Button.Pressed, "#btn-mcp")
    def on_btn_mcp(self) -> None:
        self.app.post_message(self.app.ManageMCP())

    @on(DataTable.RowSelected, "#history-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        txt_path = Path(str(event.row_key.value))
        summary_path = txt_path.with_name(txt_path.stem + "-resumo.md")

        if not summary_path.exists():
            self.app.post_message(self.app.SummarizePending(file_path=str(txt_path)))
        else:
            self.app.post_message(self.app.ViewSummary(file_path=str(summary_path)))


# ======================================================================
# Visualizador de Resumo (Markdown)
# ======================================================================


class SummaryViewerScreen(Screen):
    """
    Tela de leitura do resumo gerado em Markdown.

    Renderiza o conteudo do arquivo -resumo.md com suporte a
    tabela de conteudos, rolagem e realce de sintaxe.
    Pressione Escape ou Q para voltar ao Dashboard.
    """

    SUB_TITLE = "Visualizacao de Resumo"

    DEFAULT_CSS = """
    SummaryViewerScreen {
        layout: vertical;
    }

    #viewer-header-bar {
        height: 3;
        border-bottom: solid $primary;
        padding: 0 2;
        background: $surface;
        align: left middle;
    }

    #viewer-filename {
        color: $text-muted;
        text-style: italic;
    }

    MarkdownViewer {
        height: 1fr;
    }

    #viewer-footer-hint {
        height: 1;
        text-align: center;
        background: $surface;
        color: $text-disabled;
    }
    """

    BINDINGS = [
        Binding("escape", "go_back", "Voltar ao Dashboard", show=True),
        Binding("q", "go_back", "Voltar ao Dashboard", show=True),
        Binding("ctrl+c", "app.quit", "Sair", show=True),
    ]

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self._file_path = Path(file_path)
        # Le o arquivo no __init__ para que o conteudo fique disponivel em compose()
        try:
            self._content = self._file_path.read_text(encoding="utf-8")
        except OSError:
            self._content = ""
        # Extrai data/hora do nome do arquivo para usar no Header
        dt_str = self._file_path.stem.replace("-resumo", "").replace("transcricao_", "")
        self.TITLE = f"Resumo — {dt_str}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="viewer-header-bar"):
            yield Static(f"[dim]Arquivo:[/dim] {self._file_path.name}", id="viewer-filename")
        if self._content:
            yield MarkdownViewer(
                self._content,
                id="md-viewer",
                show_table_of_contents=True,
            )
        else:
            yield Static(
                f"[bold red]Erro:[/bold red] Nao foi possivel ler:\\n{self._file_path}",
                id="error-msg",
            )
        yield Static(
            "Pressione [bold]Esc[/bold] ou [bold]Q[/bold] para voltar",
            id="viewer-footer-hint",
        )
        yield Footer()

    def action_go_back(self) -> None:
        self.dismiss(None)
