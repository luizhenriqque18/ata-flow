"""
Ponto de entrada do AtaFlow 2.0.

Fluxo de execucao:
  1. AtaFlowApp inicia e empurra o DashboardScreen.
  2. Dashboard: usuario clica em "Nova Gravacao" -> empurra DeviceSetupScreen.
  3. Apos selecionar dispositivos -> empurra TranscriberScreen.
  4. Ctrl+S encerra a gravacao -> empurra ModelSelectionModal.
  5. Apos confirmar modelo -> gera resumo em background.
  6. Retorna ao DashboardScreen, que atualiza a lista automaticamente.

  Resumo pendente (clicado no Dashboard):
  - Dashboard detecta a linha pendente e emite SummarizePending.
  - App empurra ModelSelectionModal -> gera resumo -> volta ao Dashboard.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header

from agy_tui.app import AgyApp
from agy_tui.components import DeviceSelector, ServiceStatusBar, TranscriptionLog
from agy_tui.model_manager import ModelManagerScreen
from agy_tui.screens import (
    DashboardScreen,
    DeviceSelection,
    DeviceSetupScreen,
    ModelSelectionModal,
    SummaryViewerScreen,
)
from agy_voice.stt import WhisperLocalSTT
from audio_capture import AudioCapture
from session_manager import SessionManager
from summarizer import SummarizerFactory

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("transcriber.log", encoding="utf-8")],
)
logger = logging.getLogger("main")


# ======================================================================
# Tela de Transcricao
# ======================================================================


class TranscriberScreen(Screen[str | None]):
    """
    Tela de transcricao ativa de reuniao.
    Retorna o caminho do arquivo de saida ao encerrar (Ctrl+S), ou None.
    """

    TITLE = "AtaFlow -- Gravando"
    SUB_TITLE = "Ctrl+S para encerrar e gerar resumo"

    BINDINGS = [
        Binding("ctrl+s", "stop_session", "Encerrar e Resumir", show=True),
    ]

    def __init__(self, args: argparse.Namespace, selection: DeviceSelection) -> None:
        super().__init__()
        self.args = args
        self.selection = selection
        stt = WhisperLocalSTT(model_size=args.model, language=args.lang)
        self.session = SessionManager(
            chunk_duration=args.chunk,
            overlap=args.overlap,
            stt=stt,
        )
        self._stopping = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield DeviceSelector(id="devices")
        yield TranscriptionLog(id="log")
        yield ServiceStatusBar(id="status")
        yield Footer()

    async def on_mount(self) -> None:
        devices_widget = self.query_one(DeviceSelector)
        devices_widget.set_devices(self.selection.mic_name, self.selection.sys_name)

        status = self.query_one(ServiceStatusBar)
        status.update_whisper("carregando")
        status.update_audio("aguardando")
        status.update_llm("inativo")

        self.app.notify(
            f"Mic: {self.selection.mic_name}\nSistema: {self.selection.sys_name}",
            title="Dispositivos Ativos",
        )

        loop = asyncio.get_running_loop()
        ok = await loop.run_in_executor(
            None,
            self.session.start,
            self.selection.mic_index,
            self.selection.sys_index,
            loop,
        )

        if not ok:
            self.app.notify("Falha ao iniciar sessao. Verifique os logs.", severity="error")
            self.dismiss(None)
            return

        status.update_whisper("carregado")
        status.update_audio("capturando")

        self.run_worker(self.session.run_producer(), exclusive=False, group="audio")
        self.run_worker(self.session.run_consumer(), exclusive=False, group="audio")
        self.run_worker(self._event_listener(), exclusive=False, group="ui")

    async def _event_listener(self) -> None:
        log = self.query_one(TranscriptionLog)
        while self.session.running or not self.session.session_events.empty():
            try:
                event = await asyncio.wait_for(self.session.session_events.get(), timeout=0.5)
                if event["type"] == "transcription":
                    log.add_transcription(event["text"].strip())
            except TimeoutError:
                continue

    async def action_stop_session(self) -> None:
        if self._stopping:
            return
        self._stopping = True

        status = self.query_one(ServiceStatusBar)
        status.update_audio("parado")
        self.session.stop()
        self.app.notify(
            f"Transcricao salva em:\n{self.session.output_file}",
            title="Sessao Encerrada",
        )
        # Retorna o caminho para o App orquestrar a geracao de resumo
        self.dismiss(self.session.output_file)


# ======================================================================
# App Principal
# ======================================================================


class AtaFlowApp(AgyApp):
    """
    App central do AtaFlow 2.0.

    Orquestra a navegacao entre telas usando o sistema de Screen do Textual.
    Sempre retorna ao DashboardScreen apos qualquer acao concluida.
    """

    TITLE = "AtaFlow"
    SUB_TITLE = "Gerenciador de Atas"

    # ------------------------------------------------------------------
    # Mensagens internas (comunicacao entre telas e o App)
    # ------------------------------------------------------------------

    class ManageModels(Message):
        """Abre o gerenciador de modelos Gemini."""

    class StartNewRecording(Message):
        """Emitida pelo Dashboard para iniciar o fluxo de nova gravacao."""

    class SummarizePending(Message):
        """Emitida pelo Dashboard para reprocessar uma transcricao pendente."""

        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    class ViewSummary(Message):
        """Emitida pelo Dashboard para visualizar o resumo Markdown gerado."""

        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    # ------------------------------------------------------------------

    def __init__(
        self,
        args: argparse.Namespace,
        devices: dict,
        initial_selection: DeviceSelection | None = None,
    ) -> None:
        super().__init__()
        self.args = args
        self._devices = devices
        self.initial_selection = initial_selection

    def compose(self) -> ComposeResult:
        # O compose do App fica vazio: as Screens cuidam de Header/Footer.
        return []

    async def on_mount(self) -> None:
        if self.initial_selection:
            # Modo rapido via CLI (--mic-index / --sys-index): pula direto para gravacao.
            # O Dashboard e empurrado primeiro para que haja tela para voltar.
            await self.push_screen(DashboardScreen())
            await self.push_screen(
                TranscriberScreen(self.args, self.initial_selection),
                self._on_transcriber_done,
            )
        else:
            await self.push_screen(DashboardScreen())

    # ------------------------------------------------------------------
    # Handlers de mensagens do Dashboard
    # ------------------------------------------------------------------

    def on_ata_flow_app_manage_models(self, _: ManageModels) -> None:
        try:
            self.push_screen(ModelManagerScreen())
        except (ValueError, OSError):
            self.notify("Preferências inválidas; arquivo preservado.", severity="error")

    def on_ata_flow_app_start_new_recording(self, _: StartNewRecording) -> None:
        """Abre a tela de selecao de dispositivos de audio."""
        self.push_screen(DeviceSetupScreen(self._devices), self._on_device_selected)

    def on_ata_flow_app_summarize_pending(self, msg: SummarizePending) -> None:
        """Abre o modal de selecao de modelo para reprocessar transcricao pendente."""
        file_path = msg.file_path
        self.push_screen(
            ModelSelectionModal(self.args.provider),
            lambda res: self.run_worker(
                self._handle_model_selection(res, file_path),
                exclusive=False,
                group="summarize",
            ),
        )

    def on_ata_flow_app_view_summary(self, msg: ViewSummary) -> None:
        """Abre a tela de visualizacao de Markdown."""
        self.push_screen(SummaryViewerScreen(file_path=msg.file_path))

    # ------------------------------------------------------------------
    # Callbacks de navegacao (sempre retornam ao Dashboard)
    # ------------------------------------------------------------------

    def _on_device_selected(self, selection: DeviceSelection | None) -> None:
        """Chamado apos DeviceSetupScreen. Inicia gravacao ou volta ao Dashboard."""
        if selection:
            self.push_screen(TranscriberScreen(self.args, selection), self._on_transcriber_done)
        # Se None (usuario cancelou), simplesmente fica no Dashboard.

    def _on_transcriber_done(self, output_file: str | None) -> None:
        """
        Chamado ao encerrar a gravacao.
        Se ha arquivo de saida, abre o modal de selecao de modelo.
        Caso contrario (falha), retorna ao Dashboard e atualiza a lista.
        """
        if output_file:
            self.push_screen(
                ModelSelectionModal(self.args.provider),
                lambda res: self.run_worker(
                    self._handle_model_selection(res, output_file),
                    exclusive=False,
                    group="summarize",
                ),
            )
        else:
            self._refresh_dashboard()

    async def _handle_model_selection(self, res: tuple[str, str] | None, file_path: str) -> None:
        """
        Chamado apos ModelSelectionModal.
        Gera o resumo e, independente do resultado, volta ao Dashboard.
        """
        if res:
            provider, model = res
            await self._generate_summary(file_path, provider, model)
        else:
            self.notify("Geracao de resumo cancelada.", severity="information")

        self._refresh_dashboard()

    # ------------------------------------------------------------------
    # Geracao de resumo
    # ------------------------------------------------------------------

    async def _generate_summary(self, file_path: str, provider: str, model: str) -> None:
        """Chama o summarizer e salva o resultado. Em caso de erro, nao cria o arquivo."""
        self.notify(f"Gerando resumo com {provider.upper()} ({model})...", title="LLM")
        summarizer = SummarizerFactory.get_summarizer(provider=provider, model_name=model)
        try:
            with open(file_path, encoding="utf-8") as f:
                full_text = f.read()
            summary = await summarizer.summarize(full_text)
            summary_file = file_path.replace(".txt", "-resumo.md")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary)
            self.notify(f"Resumo salvo:\n{summary_file}", title="Resumo Gerado")
        except Exception as exc:
            logger.error(f"Erro ao gerar resumo: {exc}")
            self.notify(
                f"Erro ao gerar resumo: {exc}\nA transcricao permanece como pendente.",
                severity="error",
                timeout=8,
            )

    # ------------------------------------------------------------------
    # Utilitarios
    # ------------------------------------------------------------------

    def _refresh_dashboard(self) -> None:
        """
        Garante que o DashboardScreen esta no topo da pilha e
        atualiza sua lista de transcricoes.
        """
        # Pop todas as telas ate chegar ao DashboardScreen
        while self.screen_stack and not isinstance(self.screen, DashboardScreen):
            self.pop_screen()

        if isinstance(self.screen, DashboardScreen):
            self.screen.refresh_history()


# ======================================================================
# CLI
# ======================================================================


def parse_args() -> argparse.Namespace:
    default_provider = "gemini"
    default_model = os.environ.get("WHISPER_MODEL_SIZE", "small")
    default_lang = os.environ.get("WHISPER_LANGUAGE", "pt")
    default_chunk = float(os.environ.get("AUDIO_CHUNK_DURATION", "10.0"))
    default_overlap = float(os.environ.get("AUDIO_CHUNK_OVERLAP", "2.0"))

    p = argparse.ArgumentParser(
        description="AtaFlow - Gerador de Atas de Reunioes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python main.py                        # abre dashboard\n"
            "  python main.py --mic-index 1          # pula selecao de mic\n"
            "  python main.py --provider gemini      # provedor Gemini (unico suportado)\n"
            "  python main.py --list-devices         # lista dispositivos e sai\n"
            "  python main.py --list-llms            # lista modelos LLM e sai\n"
        ),
    )
    p.add_argument("--model", default=default_model)
    p.add_argument("--chunk", type=float, default=default_chunk)
    p.add_argument("--overlap", type=float, default=default_overlap)
    p.add_argument("--lang", default=default_lang)
    p.add_argument("--mic-index", type=int, default=None)
    p.add_argument("--sys-index", type=int, default=None)
    p.add_argument("--provider", choices=["gemini"], default=default_provider)
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--list-llms", action="store_true")
    return p.parse_args()


async def _cmd_list_llms(args: argparse.Namespace) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    from summarizer import GeminiSummarizer

    console.print("[bold cyan]Buscando modelos Gemini...[/]")
    models = await GeminiSummarizer().get_available_models()
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Modelo Gemini")
    for model in models:
        t.add_row(model)
    console.print(t)


def _cmd_list_devices() -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    devices = AudioCapture.list_devices()

    t_m = Table(title="Microfones", show_header=True, header_style="bold magenta")
    t_m.add_column("Indice", justify="right")
    t_m.add_column("Nome")
    t_m.add_column("Canais", justify="right")
    for d in devices["mics"]:
        t_m.add_row(str(d["index"]), d["name"], str(d["maxInputChannels"]))
    console.print(t_m)

    t_s = Table(title="Loopback (Sistema)", show_header=True, header_style="bold magenta")
    t_s.add_column("Indice", justify="right")
    t_s.add_column("Nome")
    t_s.add_column("Canais", justify="right")
    for d in devices["loopbacks"]:
        t_s.add_row(str(d["index"]), d["name"], str(d["maxInputChannels"]))
    console.print(t_s)


def _make_selection_from_args(
    args: argparse.Namespace,
    devices: dict,
) -> DeviceSelection | None:
    if args.mic_index is None or args.sys_index is None:
        return None
    mic_info = next((d for d in devices["mics"] if d["index"] == args.mic_index), None)
    sys_info = next((d for d in devices["loopbacks"] if d["index"] == args.sys_index), None)
    if not mic_info or not sys_info:
        return None
    return DeviceSelection(
        mic_index=mic_info["index"],
        mic_name=mic_info["name"],
        sys_index=sys_info["index"],
        sys_name=sys_info["name"],
    )


def run() -> None:
    args = parse_args()

    if args.list_devices:
        _cmd_list_devices()
        sys.exit(0)

    if args.list_llms:
        asyncio.run(_cmd_list_llms(args))
        sys.exit(0)

    devices = AudioCapture.list_devices()

    if not devices["mics"] and not devices["loopbacks"]:
        from rich.console import Console

        Console().print(
            "[bold red]Nenhum dispositivo de audio encontrado. Verifique os drivers.[/]"
        )
        sys.exit(1)

    selection = _make_selection_from_args(args, devices)
    AtaFlowApp(args, devices, selection).run()


if __name__ == "__main__":
    run()
