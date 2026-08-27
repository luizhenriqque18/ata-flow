"""
agy_voice — Integrações de voz da plataforma agy.

Fornece uma interface abstrata (Strategy Pattern) para provedores STT,
permitindo trocar a engine de transcricao sem alterar o restante do sistema.
"""
from agy_voice.interfaces import STTStrategy, TranscriptionSegment

__all__ = ["STTStrategy", "TranscriptionSegment"]
__version__ = "0.1.0"
