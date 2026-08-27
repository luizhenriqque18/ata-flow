"""
Componentes reutilizaveis da plataforma agy_tui.

Todos os widgets aqui sao desacoplados do dominio do transcritor
e podem ser importados por qualquer outra ferramenta da plataforma.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import RichLog, Static


class TranscriptionLog(RichLog):
    """
    Widget de log de transcricao em tempo real.

    Exibe linhas de texto formatadas com timestamps e tags de speaker,
    com scroll automatico e limite de linhas configuravel.
    """

    DEFAULT_CSS = """
    TranscriptionLog {
        border: round $primary;
        height: 1fr;
        scrollbar-gutter: stable;
    }
    """

    MAX_LINES: ClassVar[int] = 500

    def __init__(self, **kwargs: object) -> None:
        super().__init__(highlight=True, markup=True, max_lines=self.MAX_LINES, **kwargs)

    def add_transcription(self, text: str, speaker_tag: str = "") -> None:
        """Adiciona uma linha de transcricao formatada ao log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag_markup = f"[bold cyan]{speaker_tag}[/] " if speaker_tag else ""
        line = Text.from_markup(f"[dim]{timestamp}[/] {tag_markup}{text}")
        self.write(line)


class ServiceStatusBar(Static):
    """
    Barra de status de servicos.

    Exibe o estado dos servicos (Whisper, LLM, Audio) de forma compacta.
    """

    DEFAULT_CSS = """
    ServiceStatusBar {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    whisper_status: reactive[str] = reactive("descarregado")
    llm_status: reactive[str] = reactive("inativo")
    audio_status: reactive[str] = reactive("parado")

    def render(self) -> Text:
        """Renderiza a barra de status como uma linha Rich Text."""
        def badge(label: str, value: str, ok_values: tuple[str, ...]) -> str:
            color = "green" if value in ok_values else "red"
            return f"[{color}]●[/{color}] {label}: [bold]{value}[/]"

        return Text.from_markup(
            "  ".join([
                badge("Whisper", self.whisper_status, ("carregado", "transcrevendo")),
                badge("Audio", self.audio_status, ("capturando",)),
                badge("LLM", self.llm_status, ("pronto", "gerando")),
            ])
        )

    def update_whisper(self, status: str) -> None:
        self.whisper_status = status

    def update_audio(self, status: str) -> None:
        self.audio_status = status

    def update_llm(self, status: str) -> None:
        self.llm_status = status


class DeviceSelector(Static):
    """
    Widget simples para exibir informacoes do dispositivo de audio ativo.
    """

    DEFAULT_CSS = """
    DeviceSelector {
        height: auto;
        padding: 0 1;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[dim]Dispositivos de audio: detectando...[/]", id="device-info")

    def set_devices(self, mic_name: str, sys_name: str) -> None:
        self.query_one("#device-info", Static).update(
            f"[bold]Mic:[/] {mic_name}  [bold]Sistema:[/] {sys_name}"
        )