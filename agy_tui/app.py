"""
Classe base de aplicacao para a plataforma agy_tui.

Herdar desta classe garante que todas as ferramentas da plataforma
compartilhem o mesmo ciclo de vida, teclas de atalho globais e tema.
"""
from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

logger = logging.getLogger(__name__)


class AgyApp(App[None]):
    """
    Classe base para todas as aplicacoes da plataforma agy.

    Subclasses devem implementar compose() para definir o layout
    e on_mount() para iniciar os workers de background.
    """

    # Tema definido em theme.tcss (mesmo diretorio)
    CSS_PATH = [Path(__file__).parent / "theme.tcss"]

    # Atalhos globais compartilhados por todas as apps da plataforma
    BINDINGS = [
        Binding("ctrl+c", "quit", "Sair", show=True, priority=True),
        Binding("ctrl+l", "clear_log", "Limpar Log", show=True),
        Binding("f1", "toggle_help", "Ajuda"),
    ]

    TITLE = "agy Platform"
    SUB_TITLE = ""

    @abstractmethod
    def compose(self) -> ComposeResult:
        """Subclasses devem definir o layout da aplicacao aqui."""
        yield Header()
        yield Footer()

    def action_clear_log(self) -> None:
        """Acao padrao de limpeza de log. Subclasses podem sobrescrever."""
        try:
            log_widget = self.query_one("TranscriptionLog")
            log_widget.clear()
        except Exception:
            pass

    def action_toggle_help(self) -> None:
        """Exibe/esconde painel de ajuda."""
        self.notify("Use Ctrl+C para sair.", title="Ajuda")

    def on_error(self, event: Exception) -> None:  # type: ignore[override]
        """Handler global de erros — exibe notificacao ao usuario."""
        logger.error(f"Erro na aplicacao: {event}")
        self.notify(str(event), title="Erro", severity="error")
