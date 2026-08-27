"""
Provedor STT local usando faster-whisper.

Refatorizacao completa do transcriber.py original:
- Remove os hacks de PATH e mock do modulo av (desnecessarios com uv + .env)
- Habilita VAD nativo do faster-whisper para evitar alucinacoes no silencio
- Implementa a interface STTStrategy corretamente
- Adiciona tipagem completa (Python 3.12+)
"""
from __future__ import annotations

import logging
import os
import site

import numpy as np

from agy_voice.interfaces import STTStrategy, TranscriptionSegment

logger = logging.getLogger(__name__)


def _inject_cuda_paths() -> None:
    """
    Injeta os caminhos dos binarios CUDA/cuDNN no PATH quando necessario.

    Esta funcao e segura para executar sempre — ela verifica a existencia
    dos caminhos antes de adicioná-los, e nao usa MagicMock nem
    manipulacao de sys.modules.
    """
    try:
        paths_to_add: list[str] = []
        for site_pkg in site.getsitepackages():
            for pkg in ("cublas", "cudnn"):
                bin_path = os.path.join(site_pkg, "nvidia", pkg, "bin")
                if os.path.exists(bin_path) and bin_path not in os.environ.get("PATH", ""):
                    paths_to_add.append(bin_path)

            torch_lib = os.path.join(site_pkg, "torch", "lib")
            if os.path.exists(torch_lib) and torch_lib not in os.environ.get("PATH", ""):
                paths_to_add.append(torch_lib)

        if paths_to_add:
            os.environ["PATH"] = os.pathsep.join(paths_to_add) + os.pathsep + os.environ.get("PATH", "")
            logger.debug(f"CUDA paths adicionados ao PATH: {paths_to_add}")
    except Exception as exc:
        logger.debug(f"Falha ao injetar CUDA paths (ignorado): {exc}")


def _detect_device() -> tuple[str, str]:
    """
    Detecta se CUDA esta disponivel e retorna (device, compute_type).

    Returns:
        Tupla com ("cuda", "float16") se GPU disponivel,
        ou ("cpu", "int8") como fallback.
    """
    try:
        import ctranslate2

        supported = ctranslate2.get_supported_compute_types("cuda")
        if supported:
            logger.info("CUDA disponivel. Usando GPU (float16).")
            return "cuda", "float16"
    except Exception:
        pass

    logger.info("CUDA indisponivel. Usando CPU (int8).")
    return "cpu", "int8"


class WhisperLocalSTT(STTStrategy):
    """
    Provedor de STT usando faster-whisper rodando localmente.

    Suporta GPU (CUDA/float16) com fallback automatico para CPU (int8).
    O VAD (Voice Activity Detection) e habilitado por padrao para evitar
    alucinacoes do Whisper durante periodos de silencio.
    """

    SAMPLE_RATE: int = 16_000
    NO_SPEECH_THRESHOLD: float = 0.6  # Segmentos acima disso sao descartados

    def __init__(
        self,
        model_size: str = "small",
        language: str = "pt",
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> None:
        """
        Inicializa o provedor Whisper local.

        Args:
            model_size: Tamanho do modelo (tiny/base/small/medium/large-v3).
            language: Codigo ISO 639-1 do idioma (ex: "pt", "en").
            beam_size: Tamanho do beam search. Maior = mais lento e preciso.
            vad_filter: Habilita VAD nativo do faster-whisper.
                        Recomendado True para evitar alucinacoes no silencio.
        """
        self.model_size = model_size
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self._model: object | None = None
        self._device, self._compute_type = _detect_device()

    @property
    def sample_rate(self) -> int:
        return self.SAMPLE_RATE

    def is_available(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        """
        Carrega o modelo Whisper. Pode demorar alguns segundos na primeira vez.

        Returns:
            True se o modelo foi carregado com sucesso.
        """
        _inject_cuda_paths()

        # Agora e seguro importar faster-whisper (apos PATH pronto)
        from faster_whisper import WhisperModel

        try:
            self._model = WhisperModel(
                self.model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info(
                f"Modelo Whisper '{self.model_size}' carregado "
                f"em {self._device.upper()} ({self._compute_type})."
            )
            return True
        except Exception as exc:
            logger.error(f"Falha ao carregar modelo Whisper: {exc}")
            return False

    def transcribe(self, audio_data: np.ndarray) -> list[TranscriptionSegment]:
        """
        Transcreve um chunk de audio numpy (float32, 16kHz, mono).

        O VAD do faster-whisper filtra automaticamente os periodos de silencio,
        eliminando a necessidade do calculo RMS manual do codigo anterior.

        Args:
            audio_data: Array numpy float32 com audio mono em 16kHz.

        Returns:
            Lista de TranscriptionSegment. Retorna lista vazia se nao
            houver fala detectada ou em caso de erro.
        """
        if self._model is None:
            raise RuntimeError("Modelo nao carregado. Chame load() primeiro.")

        if len(audio_data) == 0:
            return []

        results: list[TranscriptionSegment] = []

        try:
            segments_iter, _info = self._model.transcribe(  # type: ignore[attr-defined]
                audio_data,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                vad_parameters={"min_silence_duration_ms": 500},
            )

            for seg in segments_iter:
                # Descarta segmentos com alta probabilidade de nao-fala
                if seg.no_speech_prob > self.NO_SPEECH_THRESHOLD:
                    logger.debug(f"Segmento descartado (no_speech_prob={seg.no_speech_prob:.2f})")
                    continue

                text = seg.text.strip()
                if not text:
                    continue

                results.append(
                    TranscriptionSegment(
                        start=seg.start,
                        end=seg.end,
                        text=text,
                        no_speech_prob=seg.no_speech_prob,
                    )
                )
        except Exception as exc:
            logger.error(f"Erro durante a transcricao: {exc}")

        return results

    @staticmethod
    def deduplicate(previous_text: str, current_text: str) -> str:
        """
        Remove sobreposicao de palavras entre o fim do chunk anterior
        e o inicio do chunk atual (resultado do overlap de audio).

        Args:
            previous_text: Texto do chunk anterior.
            current_text: Texto do chunk atual.

        Returns:
            Texto atual sem a sobreposicao com o anterior.
        """
        if not previous_text or not current_text:
            return current_text

        prev_words = previous_text.split()[-5:]
        curr_words = current_text.split()

        for i in range(len(prev_words)):
            prefix = prev_words[i:]
            if len(prefix) <= len(curr_words) and curr_words[: len(prefix)] == prefix:
                return " ".join(curr_words[len(prefix) :])

        return current_text
