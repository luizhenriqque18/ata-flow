"""
Interfaces abstratas (Strategy Pattern) para provedores de STT.

Qualquer novo provedor de transcricao deve herdar de STTStrategy
e implementar o metodo 	ranscribe. Isso garante que o SessionManager
seja completamente agnóstico ao backend de transcricao.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptionSegment:
    """Representa um segmento de texto transcrito com timestamps."""

    start: float
    """Tempo de inicio do segmento em segundos, relativo ao chunk."""

    end: float
    """Tempo de fim do segmento em segundos, relativo ao chunk."""

    text: str
    """Texto transcrito, ja sem espacos extras."""

    no_speech_prob: float = 0.0
    """Probabilidade de nao haver fala (0.0 a 1.0). Util para filtrar silencio."""


class STTStrategy(ABC):
    """
    Interface abstrata para provedores de Speech-to-Text.

    Implemente esta classe para adicionar novos backends de transcricao
    (ex: WhisperLocal, GroqWhisper, AssemblyAI, etc).
    """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifica se o provedor esta disponivel e pronto para uso.

        Returns:
            True se o provedor pode ser usado imediatamente.
        """

    @abstractmethod
    def load(self) -> bool:
        """
        Carrega o modelo ou establece conexao com o servico.

        Returns:
            True se o carregamento foi bem-sucedido.
        """

    @abstractmethod
    def transcribe(self, audio_data: "np.ndarray") -> list[TranscriptionSegment]:  # type: ignore[name-defined]
        """
        Transcreve um chunk de audio.

        Args:
            audio_data: Array numpy float32 com audio mono em 16kHz.

        Returns:
            Lista de segmentos transcritos. Lista vazia se nao houver fala.
        """

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Taxa de amostragem esperada pelo provedor (Hz)."""
