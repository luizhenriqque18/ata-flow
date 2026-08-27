"""
Telas (Screens) reutilizaveis da plataforma agy_tui.

DeviceSetupScreen: selecao interativa de microfone e loopback de audio
antes de iniciar qualquer sessao de captura.
"""
from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static


@dataclass
class DeviceSelection:
    """Resultado da selecao de dispositivos pelo usuario."""
    mic_index: int | None
    mic_name: str
    sys_index: int | None
    sys_name: str


class DeviceSetupScreen(Screen[DeviceSelection]):
    """
    Tela interativa de selecao de dispositivos de audio.

    Exibe duas tabelas navegaveis (microfones e loopbacks) e permite
    ao usuario escolher com setas e Enter. Retorna um DeviceSelection
    quando o usuario confirma.
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

    Button#btn-start:hover, Button#btn-start:focus {
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
        Binding("enter", "select_row", "Selecionar", show=True),
        Binding("ctrl+s", "start", "Iniciar (Atalho)", show=True),
        Binding("ctrl+c", "app.quit", "Sair", show=True),
    ]

    def __init__(self, devices: dict[str, list[dict]]) -> None:
        super().__init__()
        self._devices = devices
        self._selected_mic: dict | None = None
        self._selected_sys: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="setup-container"):
            yield Static("[bold]Transcritor Local[/bold] — Selecao de Dispositivos", id="setup-title")
            yield Static(
                "Navegue com as [bold]Setas[/] e aperte [bold]Enter[/] para confirmar cada dispositivo.",
                id="setup-hint"
            )

            with Vertical(classes="device-section"):
                yield Label("1. Microfone (sua voz):", classes="section-label")
                yield DataTable(id="mic-table", cursor_type="row", zebra_stripes=True)

            with Vertical(classes="device-section"):
                yield Label("2. Audio do Sistema (loopback — voz dos outros):", classes="section-label")
                yield DataTable(id="sys-table", cursor_type="row", zebra_stripes=True)

            yield Static("", id="selected-info")

            with Horizontal(id="btn-row"):
                yield Button("Iniciar Gravacao", id="btn-start", disabled=True, variant="success")
                yield Button("Sair", id="btn-quit", variant="error")

        yield Footer()

    def on_mount(self) -> None:
        mic_table = self.query_one("#mic-table", DataTable)
        mic_table.add_columns("Idx", "Nome", "Canais")
        for dev in self._devices.get("mics", []):
            mic_table.add_row(str(dev["index"]), dev["name"], str(dev["maxInputChannels"]), key=str(dev["index"]))

        sys_table = self.query_one("#sys-table", DataTable)
        sys_table.add_columns("Idx", "Nome", "Canais")
        for dev in self._devices.get("loopbacks", []):
            sys_table.add_row(str(dev["index"]), dev["name"], str(dev["maxInputChannels"]), key=str(dev["index"]))

        mic_table.focus()
        self._update_info()

    @on(DataTable.RowSelected, "#mic-table")
    def on_mic_selected(self, event: DataTable.RowSelected) -> None:
        mics = self._devices.get("mics", [])
        row_idx = event.cursor_row
        if row_idx < len(mics):
            self._selected_mic = mics[row_idx]
            self._update_info()
            # Foco automatico na proxima tabela apos escolher o mic
            self.query_one("#sys-table", DataTable).focus()

    @on(DataTable.RowSelected, "#sys-table")
    def on_sys_selected(self, event: DataTable.RowSelected) -> None:
        loopbacks = self._devices.get("loopbacks", [])
        row_idx = event.cursor_row
        if row_idx < len(loopbacks):
            self._selected_sys = loopbacks[row_idx]
            self._update_info()
            # Foco automatico no botao Iniciar apos escolher o sistema
            if self._selected_mic and self._selected_sys:
                self.query_one("#btn-start", Button).focus()

    def _update_info(self) -> None:
        mic_str = f"[green]✓[/] {self._selected_mic['name']}" if self._selected_mic else "[dim]Pendente...[/]"
        sys_str = f"[green]✓[/] {self._selected_sys['name']}" if self._selected_sys else "[dim]Pendente...[/]"

        self.query_one("#selected-info", Static).update(f"Mic: {mic_str}   |   Sistema: {sys_str}")
        self.query_one("#btn-start", Button).disabled = not (self._selected_mic and self._selected_sys)

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
        """Acao chamada via atalho Ctrl+S para pular para gravacao se tudo estiver ok."""
        self.on_start()

    @on(Button.Pressed, "#btn-quit")
    def on_quit(self) -> None:
        self.app.exit()