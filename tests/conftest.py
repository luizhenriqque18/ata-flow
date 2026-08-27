"""
Fixtures compartilhadas para todos os testes.

Estrategia: todos os mocks de hardware (PyAudio) e rede (httpx)
sao definidos aqui para evitar dependencias externas nos testes.
"""
from __future__ import annotations

import asyncio
import os

import numpy as np
import pytest

# Garante que os testes nao usem variaveis de ambiente reais
os.environ.setdefault("GEMINI_API_KEY", "test-key-fake")
os.environ.setdefault("LLM_PROVIDER", "ollama")


@pytest.fixture
def sample_audio_16k() -> np.ndarray:
    """Array de audio mono float32 a 16kHz com 10 segundos de sinal sintetico."""
    sample_rate = 16_000
    duration = 10
    t = np.linspace(0, duration, sample_rate * duration, dtype=np.float32)
    # Senoide simples em 440Hz simulando fala
    return (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)


@pytest.fixture
def silence_audio_16k() -> np.ndarray:
    """Array de silencio total para testar o VAD."""
    return np.zeros(16_000 * 10, dtype=np.float32)


@pytest.fixture
def mock_stt_segments():
    """Segmentos STT pre-fabricados para testes de integracao."""
    from agy_voice.interfaces import TranscriptionSegment
    return [
        TranscriptionSegment(start=0.0, end=2.5, text="Bom dia a todos", no_speech_prob=0.01),
        TranscriptionSegment(start=2.5, end=5.0, text="Vamos comecar a reuniao", no_speech_prob=0.02),
    ]
