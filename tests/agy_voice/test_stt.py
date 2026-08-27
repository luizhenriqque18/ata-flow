"""
Testes unitarios para a interface STT e o provedor WhisperLocalSTT.

Nao carrega o modelo Whisper real — usa mocks para validar
os contratos da interface sem gastar memoria ou tempo de GPU.
"""
from __future__ import annotations

import numpy as np
import pytest
from pytest_mock import MockerFixture

from agy_voice.interfaces import STTStrategy, TranscriptionSegment
from agy_voice.stt import WhisperLocalSTT


# --- Testes da Interface / Contrato ---

class DummySTT(STTStrategy):
    """Implementacao minima para testar a interface abstrata."""

    def is_available(self) -> bool:
        return True

    def load(self) -> bool:
        return True

    def transcribe(self, audio_data: np.ndarray) -> list[TranscriptionSegment]:
        return [TranscriptionSegment(start=0.0, end=1.0, text="teste")]

    @property
    def sample_rate(self) -> int:
        return 16_000


def test_stt_interface_contract() -> None:
    """Garante que a interface pode ser instanciada e usada corretamente."""
    stt = DummySTT()
    assert stt.is_available()
    assert stt.load()
    assert stt.sample_rate == 16_000
    segments = stt.transcribe(np.zeros(100, dtype=np.float32))
    assert len(segments) == 1
    assert segments[0].text == "teste"


def test_transcription_segment_immutability() -> None:
    """TranscriptionSegment deve ser frozen (imutavel)."""
    seg = TranscriptionSegment(start=0.0, end=1.0, text="hello")
    with pytest.raises(Exception):  # FrozenInstanceError ou AttributeError
        seg.text = "modified"  # type: ignore[misc]


# --- Testes do WhisperLocalSTT ---

def test_whisper_not_available_before_load() -> None:
    """Whisper nao deve estar disponivel antes de chamar load()."""
    stt = WhisperLocalSTT()
    assert not stt.is_available()


def test_whisper_transcribe_raises_without_load(sample_audio_16k: np.ndarray) -> None:
    """Transcricao deve levantar RuntimeError se o modelo nao foi carregado."""
    stt = WhisperLocalSTT()
    with pytest.raises(RuntimeError, match="Chame load\\(\\) primeiro"):
        stt.transcribe(sample_audio_16k)


def test_whisper_load_mocked(mocker: MockerFixture) -> None:
    """Simula o carregamento do modelo sem instanciar o Whisper real.

    WhisperModel e importado de forma lazy dentro de load() para evitar
    falhas em ambientes sem GPU. Por isso, fazemos o mock no modulo
    faster_whisper diretamente.
    """
    mock_model = mocker.MagicMock()
    # Mocka no modulo fonte, onde o import lazy vai buscar
    mocker.patch("faster_whisper.WhisperModel", return_value=mock_model)

    # Evita efeitos colaterais de ambiente
    mocker.patch("agy_voice.stt.whisper_local._inject_cuda_paths")
    mocker.patch("agy_voice.stt.whisper_local._detect_device", return_value=("cpu", "int8"))

    from agy_voice.stt.whisper_local import WhisperLocalSTT as _STT

    stt = _STT(model_size="tiny")
    result = stt.load()

    assert result is True
    assert stt.is_available()


def test_whisper_transcribe_mocked(mocker: MockerFixture, sample_audio_16k: np.ndarray) -> None:
    """Simula uma transcricao bem-sucedida sem rodar o Whisper real."""
    from unittest.mock import MagicMock

    # Cria segmento falso que imita a API do faster-whisper
    fake_segment = MagicMock()
    fake_segment.start = 0.0
    fake_segment.end = 3.0
    fake_segment.text = "  Ola mundo  "
    fake_segment.no_speech_prob = 0.01

    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter([fake_segment]), MagicMock())

    stt = WhisperLocalSTT()
    stt._model = mock_model

    segments = stt.transcribe(sample_audio_16k)

    assert len(segments) == 1
    assert segments[0].text == "Ola mundo"  # strip() aplicado
    assert segments[0].start == 0.0
    assert segments[0].end == 3.0


def test_whisper_filters_no_speech(mocker: MockerFixture, sample_audio_16k: np.ndarray) -> None:
    """Segmentos com alta no_speech_prob devem ser descartados."""
    from unittest.mock import MagicMock

    fake_segment = MagicMock()
    fake_segment.start = 0.0
    fake_segment.end = 5.0
    fake_segment.text = "alucinacao do modelo"
    fake_segment.no_speech_prob = 0.95  # acima do threshold de 0.6

    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter([fake_segment]), MagicMock())

    stt = WhisperLocalSTT()
    stt._model = mock_model

    segments = stt.transcribe(sample_audio_16k)
    assert len(segments) == 0


def test_deduplicate_removes_overlap() -> None:
    """Deduplicacao deve remover palavras sobrepostas entre chunks."""
    prev = "Bom dia a todos nos"
    curr = "todos nos vamos comecar"
    result = WhisperLocalSTT.deduplicate(prev, curr)
    assert result == "vamos comecar"


def test_deduplicate_no_overlap() -> None:
    """Sem sobreposicao, retorna o texto atual inteiro."""
    prev = "um dois tres"
    curr = "quatro cinco seis"
    result = WhisperLocalSTT.deduplicate(prev, curr)
    assert result == curr


def test_deduplicate_empty_inputs() -> None:
    """Entradas vazias devem retornar o texto atual sem erros."""
    assert WhisperLocalSTT.deduplicate("", "algum texto") == "algum texto"
    assert WhisperLocalSTT.deduplicate("algum texto", "") == ""
