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
    from config import get_default
    default_provider = get_default("provider", "ollama")
    default_llm = get_default(f"llm_{default_provider}", "llama3.2:1b" if default_provider == "ollama" else "gemini-3.5-flash")

    parser = argparse.ArgumentParser(description="Transcritor Local CLI (Microfone + WASAPI)")
    parser.add_argument("--model", type=str, default="small", help="Tamanho do modelo whisper (default: small)")
    parser.add_argument("--chunk", type=float, default=10.0, help="Duração do chunk em segundos (default: 10)")
    parser.add_argument("--overlap", type=float, default=2.0, help="Sobreposição entre chunks em segundos (default: 2)")
    parser.add_argument("--lang", type=str, default="pt", help="Idioma para transcrição (default: pt)")
    parser.add_argument("--list-devices", action="store_true", help="Lista os dispositivos de áudio disponíveis e sai")
    parser.add_argument("--mic-index", type=int, default=None, help="Índice do microfone a ser capturado")
    parser.add_argument("--sys-index", type=int, default=None, help="Índice do loopback de áudio do sistema")
    parser.add_argument("--llm", type=str, default=default_llm, help=f"Modelo LLM para gerar o resumo (default salvo: {default_llm})")
    parser.add_argument("--list-llms", action="store_true", help="Lista os modelos LLM do provedor atual e sai")
    parser.add_argument("--set-gemini-key", type=str, default=None, help="Salva a chave de API do Gemini no config.json")
    parser.add_argument("--provider", type=str, choices=["ollama", "gemini"], default=default_provider, help=f"Qual IA usar para o resumo (default salvo: {default_provider})")
    parser.add_argument("--set-default-provider", type=str, choices=["ollama", "gemini"], default=None, help="Salva o provedor padrao no config.json")
    parser.add_argument("--set-default-llm", type=str, default=None, help="Salva o modelo LLM padrao para o provedor atual no config.json")
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

    def run(self):
        signal.signal(signal.SIGINT, self.handle_sigint)
        
        if self.args.model in ["medium", "large", "large-v2", "large-v3"]:
            console.print(Panel(f"[bold yellow]AVISO DE VRAM[/]\nO modelo '{self.args.model}' pode exceder o limite de 4GB da sua GPU. Se ocorrerem travamentos, use o modelo 'small'.", border_style="yellow"))
            time.sleep(2)
            
        console.print(Panel("[bold green]Iniciando Transcritor Local CLI[/]\nAguarde o carregamento do modelo...", expand=False))
        
        if not self.session.start(mic_index=self.args.mic_index, sys_index=self.args.sys_index):
            console.print("[bold red]Falha ao iniciar a sessão. Verifique os logs e os índices dos dispositivos.[/]")
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
            layout["body"].update(Panel(text_body, title="[yellow]Transcrição Contínua (Pressione Ctrl+C para encerrar e gerar resumo)[/]"))
            
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
                
        console.print("\n[bold red]Interrupção detectada (Ctrl+C). Encerrando a sessão e processando o áudio final...[/]")
        self.session.stop()
        console.print(f"[bold green]Sessão de transcrição encerrada. Arquivo bruto salvo em:[/] {self.session.output_file}")
        
        # Etapa de Resumo Local
        from summarizer import SummarizerFactory
        summarizer = SummarizerFactory.get_summarizer(provider=self.args.provider, model_name=self.args.llm)
        
        if summarizer.is_available():
            console.print(Panel(f"[bold cyan]🤖 Gerando Resumo Inteligente com {self.args.provider.upper()}...[/]\nIsso pode levar alguns minutos dependendo do tamanho da reunião.", expand=False))
            
            try:
                with open(self.session.output_file, "r", encoding="utf-8") as f:
                    full_text = f.read()
                    
                summary = summarizer.summarize(full_text)
                
                summary_file = self.session.output_file.replace(".txt", "-resumo.md")
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write(summary)
                    
                console.print(f"[bold green]✅ Resumo em Markdown salvo com sucesso em:[/] {summary_file}")
            except Exception as e:
                console.print(f"[bold red]Erro ao processar o resumo: {e}[/]")
        else:
            console.print("[dim yellow]Serviço do Ollama não detectado. O resumo inteligente em Markdown foi ignorado. (Instale o Ollama para habilitar esta função)[/]")

if __name__ == "__main__":
    args = parse_args()
    
    if args.set_gemini_key:
        from config import set_gemini_key
        if set_gemini_key(args.set_gemini_key):
            console.print("[bold green]Chave de API do Gemini salva com sucesso em config.json![/]")
        else:
            console.print("[bold red]Erro ao tentar salvar a chave do Gemini.[/]")
        sys.exit(0)
        
    if args.set_default_provider:
        from config import set_default
        set_default("provider", args.set_default_provider)
        console.print(f"[bold green]Provedor padrão salvo como '{args.set_default_provider}' em config.json![/]")
        sys.exit(0)
        
    if args.set_default_llm:
        from config import set_default
        set_default(f"llm_{args.provider}", args.set_default_llm)
        console.print(f"[bold green]Modelo LLM padrão para '{args.provider}' salvo como '{args.set_default_llm}' em config.json![/]")
        sys.exit(0)

    if args.list_llms:
        from rich.table import Table
        if args.provider == "gemini":
            from summarizer import GeminiSummarizer
            models = GeminiSummarizer.get_available_models()
            provider_name = "Gemini"
        else:
            from summarizer import OllamaSummarizer
            models = OllamaSummarizer.get_available_models()
            provider_name = "Ollama"
            
        if not models:
            console.print(f"[bold red]{provider_name} não configurado ou inacessível. Verifique a chave da API ou se o serviço está rodando.[/]")
        else:
            console.print(f"\n[bold cyan]Modelos LLM disponíveis ({provider_name})[/]")
            t_llms = Table(show_header=True, header_style="bold magenta")
            t_llms.add_column("Nome do Modelo")
            for m in models:
                t_llms.add_row(m)
            console.print(t_llms)
            console.print("\nPara salvar um modelo como padrão, use:")
            console.print(f"[bold yellow]python main.py --provider {args.provider} --set-default-llm <Nome>[/]")
        sys.exit(0)
        
    if args.list_devices:
        from audio_capture import AudioCapture
        from rich.table import Table
        
        devices = AudioCapture.list_devices()
        
        console.print("\n[bold cyan]Dispositivos de Captura (Microfones)[/]")
        t_mics = Table(show_header=True, header_style="bold magenta")
        t_mics.add_column("Índice", style="dim", justify="right")
        t_mics.add_column("Nome")
        t_mics.add_column("Canais", justify="right")
        for d in devices["mics"]:
            t_mics.add_row(str(d["index"]), d["name"], str(d["maxInputChannels"]))
        console.print(t_mics)
        
        console.print("\n[bold cyan]Dispositivos de Loopback (Áudio do Sistema)[/]")
        t_sys = Table(show_header=True, header_style="bold magenta")
        t_sys.add_column("Índice", style="dim", justify="right")
        t_sys.add_column("Nome")
        t_sys.add_column("Canais", justify="right")
        for d in devices["loopbacks"]:
            t_sys.add_row(str(d["index"]), d["name"], str(d["maxInputChannels"]))
        console.print(t_sys)
        
        sys.exit(0)
        
    app = AppCLI(args)
    app.run()

