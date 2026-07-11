import sys
import time
import signal
import argparse
import logging
from queue import Empty
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout

from session_manager import SessionManager

# Configuração de log para não poluir a tela principal (salvando em arquivo)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("transcriber.log", encoding="utf-8")]
)
logger = logging.getLogger("main")

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Transcritor Local CLI (Microfone + WASAPI)")
    parser.add_argument("--model", type=str, default="small", help="Tamanho do modelo whisper (default: small)")
    parser.add_argument("--chunk", type=float, default=10.0, help="Duração do chunk em segundos (default: 10)")
    parser.add_argument("--overlap", type=float, default=2.0, help="Sobreposição entre chunks em segundos (default: 2)")
    parser.add_argument("--lang", type=str, default="pt", help="Idioma para transcrição (default: pt)")
    return parser.parse_args()

class AppCLI:
    def __init__(self, args):
        self.args = args
        self.session = SessionManager(
            chunk_duration=args.chunk,
            overlap=args.overlap
        )
        self.session.transcriber.model_size = args.model
        self.session.transcriber.language = args.lang
        self.running = False

    def handle_sigint(self, sig, frame):
        if not self.running:
            return
        self.running = False
        console.print("\n[bold red]Interrupção detectada (Ctrl+C). Iniciando encerramento seguro...[/]")
        self.session.stop()
        sys.exit(0)

    def run(self):
        signal.signal(signal.SIGINT, self.handle_sigint)
        
        console.print(Panel("[bold green]Iniciando Transcritor Local CLI[/]\nAguarde o carregamento do modelo...", expand=False))
        
        if not self.session.start():
            console.print("[bold red]Falha ao iniciar a sessão. Verifique os logs.[/]")
            return

        self.running = True
        
        console.clear()
        
        transcription_history = []
        
        def generate_layout():
            layout = Layout()
            layout.split(
                Layout(name="header", size=3),
                Layout(name="body")
            )
            
            # Header
            status = f"Backend: {self.session.transcriber.device.upper()} | Filas: Mic {self.session.audio_capture.mic_queue.qsize()} Sys {self.session.audio_capture.sys_queue.qsize()} Transc {self.session.transcription_queue.qsize()}"
            layout["header"].update(Panel(f"[bold cyan]Transcritor Local em Execução[/] - {status}"))
            
            # Body
            text_body = "".join(transcription_history[-15:])  # Últimas 15 linhas
            layout["body"].update(Panel(text_body, title="[yellow]Transcrição Contínua[/]"))
            
            return layout

        with Live(generate_layout(), refresh_per_second=4, console=console) as live:
            while self.running:
                try:
                    event = self.session.session_events.get(timeout=0.25)
                    if event["type"] == "transcription":
                        transcription_history.append(event["text"])
                        
                except Empty:
                    pass
                
                if not self.session.running:
                    self.running = False
                    
                live.update(generate_layout())
                
        console.print("[bold green]Sessão encerrada com segurança. Arquivo salvo em ./transcricoes/[/]")

if __name__ == "__main__":
    args = parse_args()
    app = AppCLI(args)
    app.run()

