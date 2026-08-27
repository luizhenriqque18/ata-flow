"""
Gerenciador de sessao de transcricao de reunioes.

Refatoracao em relacao ao original:
- Loop de producao e consumo agora sao corrotinas asyncio (async def)
- Remove logica de VAD manual por RMS (agora feito pelo Whisper via vad_filter)
- Simplifica o buffer de audio e a uniao dos canais
- Usa asyncio.Queue em vez de queue.Queue
- Aceita qualquer STTStrategy — desacoplado do Whisper
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import numpy as np

from audio_capture import AudioCapture
from agy_voice.interfaces import STTStrategy, TranscriptionSegment
from agy_voice.stt import WhisperLocalSTT

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Orquestra a captura de audio, a transcricao e a persistencia em arquivo.

    O fluxo de dados e:
    AudioCapture (callbacks) --> asyncio.Queue --> _producer --> _transcription_queue --> _consumer
    """

    def __init__(
        self,
        chunk_duration: float = 10.0,
        overlap: float = 2.0,
        max_queue_size: int = 10,
        stt: STTStrategy | None = None,
    ) -> None:
        self.chunk_duration = chunk_duration
        self.overlap = overlap

        self.audio_capture = AudioCapture()
        self.stt: STTStrategy = stt or WhisperLocalSTT()

        self._transcription_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=max_queue_size)

        self.running = False

        output_dir = "./transcricoes"
        os.makedirs(output_dir, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%Hh%M-reuniao.txt")
        self.output_file = os.path.join(output_dir, filename)

        self._last_text = ""

        # Fila de eventos consumida pela TUI para exibir a transcricao
        self.session_events: asyncio.Queue[dict] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def start(self, mic_index: int | None = None, sys_index: int | None = None, loop: "asyncio.AbstractEventLoop | None" = None) -> bool:
        """
        Carrega o modelo STT e inicia a captura de audio.

        Returns:
            True se a sessao foi iniciada com sucesso.
        """
        logger.info("Carregando modelo STT...")
        if not self.stt.load():
            logger.error("Falha ao carregar modelo STT.")
            return False

        self.running = True
        self.audio_capture.start(mic_index=mic_index, sys_index=sys_index, loop=loop)
        logger.info("Sessao iniciada.")
        return True

    def stop(self) -> None:
        """Para a captura e sinaliza o fim da sessao."""
        logger.info("Encerrando sessao...")
        self.running = False
        self.audio_capture.stop()
        logger.info("Sessao encerrada.")

    # ------------------------------------------------------------------
    # Corrotinas assincronas de processamento
    # ------------------------------------------------------------------

    async def run_producer(self) -> None:
        """
        Corrotina que acumula audio das filas e despacha chunks para transcricao.

        Substitui o antigo _producer_loop (threading.Thread).
        Sem polling de RMS — a deteccao de voz e delegada ao VAD do Whisper.
        """
        sample_rate = self.audio_capture.sample_rate
        chunk_samples = int(self.chunk_duration * sample_rate)
        step_samples = chunk_samples - int(self.overlap * sample_rate)

        mic_buffer = np.array([], dtype=np.float32)
        sys_buffer = np.array([], dtype=np.float32)

        while self.running:
            # Drena as filas de audio sem bloquear
            while not self.audio_capture.mic_queue.empty():
                mic_buffer = np.concatenate([mic_buffer, self.audio_capture.mic_queue.get_nowait()])
            while not self.audio_capture.sys_queue.empty():
                sys_buffer = np.concatenate([sys_buffer, self.audio_capture.sys_queue.get_nowait()])

            if len(mic_buffer) >= chunk_samples or len(sys_buffer) >= chunk_samples:
                mic_chunk = mic_buffer[:chunk_samples] if len(mic_buffer) > 0 else np.array([], dtype=np.float32)
                sys_chunk = sys_buffer[:chunk_samples] if len(sys_buffer) > 0 else np.array([], dtype=np.float32)

                mixed = AudioCapture.mix_and_normalize(mic_chunk, sys_chunk)
                if len(mixed) < chunk_samples:
                    pad = np.zeros(chunk_samples, dtype=np.float32)
                    pad[: len(mixed)] = mixed
                    mixed = pad

                if self._transcription_queue.full():
                    logger.warning("Fila de transcricao cheia. Descartando chunk mais antigo.")
                    try:
                        self._transcription_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass

                await self._transcription_queue.put({"audio": mixed})

                mic_buffer = mic_buffer[step_samples:]
                sys_buffer = sys_buffer[step_samples:]

            await asyncio.sleep(0.1)

    async def run_consumer(self) -> None:
        """
        Corrotina que transcreve os chunks da fila e emite eventos para a TUI.

        Executa o Whisper em um executor para nao bloquear o event loop.
        """
        loop = asyncio.get_running_loop()

        while self.running or not self._transcription_queue.empty():
            try:
                item = await asyncio.wait_for(self._transcription_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            audio_data: np.ndarray = item["audio"]

            # Whisper e CPU/GPU bound — executar fora do event loop
            segments: list[TranscriptionSegment] = await loop.run_in_executor(
                None, self.stt.transcribe, audio_data
            )

            if segments:
                full_text = " ".join(s.text for s in segments)
                deduped = WhisperLocalSTT.deduplicate(self._last_text, full_text)
                self._last_text = deduped

                if deduped.strip():
                    start_str = self._fmt_time(segments[0].start)
                    end_str = self._fmt_time(segments[-1].end)
                    formatted = f"[{start_str} - {end_str}] {deduped}\n"
                    self._save_line(formatted)
                    await self.session_events.put({"type": "transcription", "text": formatted})

            self._transcription_queue.task_done()

    # ------------------------------------------------------------------
    # Utilitarios privados
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _save_line(self, text: str) -> None:
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(text)
        except OSError as exc:
            logger.error(f"Erro ao salvar no arquivo: {exc}")
