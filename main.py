"""
Ponto de entrada do Transcritor Local CLI.

Fluxo de execucao:
  1. Detecta os dispositivos de audio disponiveis
  2. Exibe DeviceSetupScreen para o usuario escolher mic e loopback
  3. Inicia o TranscriberApp com os dispositivos selecionados
  4. Ao encerrar (Ctrl+C ou Ctrl+S), gera o resumo LLM automaticamente
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
from textual.widgets import Footer, Header, Static

from agy_tui.app import AgyApp
from agy_tui.components import DeviceSelector, ServiceStatusBar, TranscriptionLog
from agy_tui.screens import DeviceSelection, DeviceSetupScreen
from audio_capture import AudioCapture
from agy_voice.stt import WhisperLocalSTT
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
# App principal de transcricao
# ======================================================================

class TranscriberApp(AgyApp):
    """Aplicacao principal de transcricao de reunioes."""

    TITLE = "AtaFlow"
    SUB_TITLE = "Ctrl+S para encerrar e gerar resumo"

    BINDINGS = [
        *AgyApp.BINDINGS,
        Binding("ctrl+s", "stop_session", "Encerrar e Resumir", show=True),
    ]

    def __init__(self, args: argparse.Namespace, selection: DeviceSelection) -> None:
        super().__init__()
        self.args = args
        self.selection = selection
        stt = WhisperLocalSTT(
            model_size=args.model,
            language=args.lang,
        )
        self.session = SessionManager(
            chunk_duration=args.chunk,
            overlap=args.overlap,
            stt=stt,
        )
        self._stopping = False

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield DeviceSelector(id="devices")
        yield TranscriptionLog(id="log")
        yield ServiceStatusBar(id="status")
        yield Footer()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def on_mount(self) -> None:
        # Exibe dispositivos selecionados no widget
        devices_widget = self.query_one(DeviceSelector)
        devices_widget.set_devices(self.selection.mic_name, self.selection.sys_name)

        status = self.query_one(ServiceStatusBar)
        status.update_whisper("carregando")
        status.update_audio("aguardando")
        status.update_llm("inativo")

        self.notify(
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
            self.notify("Falha ao iniciar sessao. Verifique os logs.", severity="error")
            await self.action_quit()
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
            except asyncio.TimeoutError:
                continue

    # ------------------------------------------------------------------
    # Acoes
    # ------------------------------------------------------------------

    async def action_stop_session(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        await self._finalize()

    async def action_quit(self) -> None:
        if not self._stopping:
            self._stopping = True
            await self._finalize()
        self.exit()

    async def _finalize(self) -> None:
        status = self.query_one(ServiceStatusBar)
        status.update_audio("parado")
        self.session.stop()
        self.notify(f"Transcricao salva em:\n{self.session.output_file}", title="Sessao Encerrada")

        provider = self.args.provider
        summarizer = SummarizerFactory.get_summarizer(provider=provider)

        if provider == "gemini":
            if not summarizer.is_available():
                self.notify("GEMINI_API_KEY nao configurada. Resumo ignorado.", severity="warning")
                return
            status.update_llm("verificando")
            ok, stable_model = await summarizer.verify_and_fallback()
            if not ok:
                self.notify("Nenhum modelo Gemini disponivel.", severity="error")
                return
            summarizer.model_name = stable_model

        status.update_llm("gerando")
        self.notify(f"Gerando resumo com {provider.upper()}...", title="LLM")

        try:
            with open(self.session.output_file, encoding="utf-8") as f:
                full_text = f.read()
            summary = await summarizer.summarize(full_text)
            summary_file = self.session.output_file.replace(".txt", "-resumo.md")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary)
            status.update_llm("pronto")
            self.notify(f"Resumo salvo:\n{summary_file}", title="Resumo Gerado")
        except Exception as exc:
            logger.error(f"Erro ao gerar resumo: {exc}")
            self.notify(f"Erro: {exc}", severity="error")


# ======================================================================
# App de selecao de dispositivos (ponto de entrada unificado)
# ======================================================================

class LauncherApp(AgyApp):
    """
    App de entrada que gerencia a selecao de dispositivos e o launch
    da sessao de transcricao, tudo no mesmo terminal.
    """

    TITLE = "AtaFlow — Setup"

    def __init__(self, args: argparse.Namespace, devices: dict) -> None:
        super().__init__()
        self.args = args
        self._devices = devices

    def compose(self) -> ComposeResult:
        # Tela de setup sera exibida via push_screen no on_mount
        yield Header()
        yield Static("")
        yield Footer()

    async def on_mount(self) -> None:
        """Abre a tela de selecao de dispositivos imediatamente."""
        def on_selection(selection: DeviceSelection | None) -> None:
            if selection is None:
                # Usuario saiu sem confirmar
                self.exit()
                return
            # Troca para o app de transcricao no mesmo terminal
            self.exit(result=selection)

        await self.push_screen(
            DeviceSetupScreen(self._devices),
            callback=on_selection,
        )


# ======================================================================
# CLI
# ======================================================================

def parse_args() -> argparse.Namespace:
    default_provider = os.environ.get("LLM_PROVIDER", "ollama")
    default_model = os.environ.get("WHISPER_MODEL_SIZE", "small")
    default_lang = os.environ.get("WHISPER_LANGUAGE", "pt")
    default_chunk = float(os.environ.get("AUDIO_CHUNK_DURATION", "10.0"))
    default_overlap = float(os.environ.get("AUDIO_CHUNK_OVERLAP", "2.0"))

    p = argparse.ArgumentParser(
        description="AtaFlow - Gerador de Atas de Reunioes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python main.py                        # selecao interativa de dispositivos\n"
            "  python main.py --mic-index 1          # pula selecao de mic\n"
            "  python main.py --provider gemini      # resumo via Gemini\n"
            "  python main.py --list-devices         # lista dispositivos e sai\n"
            "  python main.py --list-llms            # lista modelos LLM e sai\n"
        ),
    )
    p.add_argument("--model", default=default_model, help=f"Tamanho do modelo Whisper (default: {default_model})")
    p.add_argument("--chunk", type=float, default=default_chunk)
    p.add_argument("--overlap", type=float, default=default_overlap)
    p.add_argument("--lang", default=default_lang, help=f"Idioma (default: {default_lang})")
    p.add_argument("--mic-index", type=int, default=None, help="Pular selecao: indice do microfone")
    p.add_argument("--sys-index", type=int, default=None, help="Pular selecao: indice do loopback do sistema")
    p.add_argument("--provider", choices=["ollama", "gemini"], default=default_provider)
    p.add_argument("--list-devices", action="store_true", help="Lista dispositivos e sai")
    p.add_argument("--list-llms", action="store_true", help="Lista modelos LLM do provedor e sai")
    return p.parse_args()


async def _cmd_list_llms(args: argparse.Namespace) -> None:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    if args.provider == "gemini":
        from summarizer import GeminiSummarizer
        console.print("[bold cyan]Executando HealthCheck nos modelos Gemini...[/]")
        models = await GeminiSummarizer.get_available_models(health_check=True)
        t = Table(show_header=True, header_style="bold magenta")
        t.add_column("Modelo")
        t.add_column("Status")
        for m in models:
            t.add_row(m["name"], m["status"])
    else:
        from summarizer import OllamaSummarizer
        models = await OllamaSummarizer.get_available_models()
        t = Table(show_header=True, header_style="bold magenta")
        t.add_column("Modelo Ollama")
        for m in models:
            t.add_row(m)
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
    """
    Se --mic-index e --sys-index foram passados, cria uma DeviceSelection
    diretamente sem abrir a tela de setup.
    """
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

    # Detecta dispositivos antes de abrir qualquer TUI
    devices = AudioCapture.list_devices()

    if not devices["mics"] and not devices["loopbacks"]:
        from rich.console import Console
        Console().print("[bold red]Nenhum dispositivo de audio encontrado. Verifique os drivers.[/]")
        sys.exit(1)

    # Verifica se args ja tem dispositivos definidos (modo rapido/CI)
    selection = _make_selection_from_args(args, devices)

    if selection is None:
        # Modo interativo: abre tela de selecao de dispositivos
        launcher = LauncherApp(args, devices)
        selection = launcher.run()

    if selection is None:
        # Usuario saiu da tela de setup sem confirmar
        sys.exit(0)

    # Inicia o app de transcricao com os dispositivos escolhidos
    TranscriberApp(args, selection).run()


if __name__ == "__main__":
    run()