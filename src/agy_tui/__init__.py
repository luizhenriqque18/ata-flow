"""
agy_tui — Biblioteca base de TUI da plataforma agy.

Fornece app base, componentes reutilizaveis, telas e tema visual padronizado
construidos sobre o framework Textual.
"""

from agy_tui.app import AgyApp
from agy_tui.components import DeviceSelector, ServiceStatusBar, TranscriptionLog
from agy_tui.screens import (
    DashboardScreen,
    DeviceSelection,
    DeviceSetupScreen,
    ModelSelectionModal,
    SummaryViewerScreen,
)

__all__ = [
    "AgyApp",
    "TranscriptionLog",
    "ServiceStatusBar",
    "DeviceSelector",
    "DeviceSetupScreen",
    "DeviceSelection",
    "DashboardScreen",
    "ModelSelectionModal",
    "SummaryViewerScreen",
]
__version__ = "0.2.0"
