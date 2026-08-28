"""
agy_tui — Biblioteca base de TUI da plataforma agy.

Fornece app base, componentes reutilizaveis, telas e tema visual padronizado
construidos sobre o framework Textual.
"""
from agy_tui.app import AgyApp
from agy_tui.components import TranscriptionLog, ServiceStatusBar, DeviceSelector
from agy_tui.screens import (
    DeviceSetupScreen,
    DeviceSelection,
    DashboardScreen,
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