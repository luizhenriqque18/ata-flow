"""Ciclo de vida da captura, transcrição e persistência de uma reunião."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from agy_voice.interfaces import STTStrategy, TranscriptionSegment
from agy_voice.processing import deduplicate
from ataflow.recording.capture import AudioCapture

logger = logging.getLogger(__name__)


class SessionManager:
    """Uma sessão controla seus produtores/consumidores até a escrita final."""

    def __init__(
        self,
        chunk_duration: float = 10.0,
        overlap: float = 2.0,
        max_queue_size: int = 10,
        *,
        stt: STTStrategy,
        audio_capture: AudioCapture | None = None,
        output_dir: str | Path = "./transcricoes",
    ) -> None:
        if chunk_duration <= 0 or not 0 <= overlap < chunk_duration or max_queue_size <= 0:
            raise ValueError("Use duração positiva, 0 <= overlap < duração e fila positiva.")
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.stt = stt
        self.audio_capture = audio_capture or AudioCapture(sample_rate=self.stt.sample_rate)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%Hh%M-%S-%f-reuniao.txt")
        self.output_file = str(self.output_dir / filename)
        self._transcription_queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue(max_queue_size)
        self.session_events: asyncio.Queue[dict] = asyncio.Queue()
        self.running = False
        self._last_text = ""
        self._processing_task: asyncio.Task | None = None
        self._processing_error: Exception | None = None
        self._finished = asyncio.Event()
        self._lifecycle_lock = asyncio.Lock()
        self._capture_stop_lock = asyncio.Lock()
        self._capture_stopped = False
        self._started = False

    @property
    def finished(self) -> bool:
        return self._finished.is_set()

    async def start(self, mic_index: int | None = None, sys_index: int | None = None) -> bool:
        """Carrega o STT fora do loop e inicia as tarefas pertencentes à sessão."""
        async with self._lifecycle_lock:
            if self._started:
                raise RuntimeError("Esta sessão já foi iniciada. Crie outra para gravar novamente.")
            self._started = True
            try:
                if not await asyncio.to_thread(self.stt.load):
                    await self._stop_capture()
                    self._finished.set()
                    return False
                await asyncio.to_thread(
                    self.audio_capture.start,
                    mic_index=mic_index,
                    sys_index=sys_index,
                    loop=asyncio.get_running_loop(),
                )
                self.running = True
                self._processing_task = asyncio.create_task(self._process())
                return True
            except Exception:
                await self._stop_capture()
                self._finished.set()
                raise

    async def _stop_capture(self) -> None:
        async with self._capture_stop_lock:
            try:
                if not self._capture_stopped:
                    await asyncio.to_thread(self.audio_capture.stop)
                    self._capture_stopped = True
                    # Entrega os últimos callbacks agendados via call_soon_threadsafe.
                    await asyncio.sleep(0)
            finally:
                self.running = False

    async def finish(self) -> str:
        """Para a captura e aguarda a persistência, inclusive em chamadas repetidas."""
        async with self._lifecycle_lock:
            await self._stop_capture()
            if self._processing_task:
                await asyncio.shield(self._processing_task)
            else:
                self._finished.set()
            if self._processing_error:
                raise RuntimeError(
                    "Não foi possível concluir a transcrição."
                ) from self._processing_error
            return self.output_file

    async def _process(self) -> None:
        try:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(self.run_producer())
                tasks.create_task(self.run_consumer())
        except Exception as exc:
            self._processing_error = exc
            logger.exception("Falha no processamento da sessão")
            await self._stop_capture()
            await self.session_events.put({"type": "error", "text": "Falha na transcrição."})
        finally:
            self._finished.set()

    async def run_producer(self) -> None:
        """Envia blocos completos e a cauda final; None sinaliza o fim ao consumidor."""
        sample_rate = self.audio_capture.sample_rate
        chunk_samples = int(self.chunk_duration * sample_rate)
        overlap_samples = int(self.overlap * sample_rate)
        step_samples = chunk_samples - overlap_samples
        if chunk_samples <= 0 or step_samples <= 0:
            raise ValueError("Duração insuficiente para a taxa de amostragem.")
        mic_buffer = np.array([], dtype=np.float32)
        sys_buffer = np.array([], dtype=np.float32)
        retained_overlap = 0
        while True:
            while not self.audio_capture.mic_queue.empty():
                mic_buffer = np.concatenate([mic_buffer, self.audio_capture.mic_queue.get_nowait()])
            while not self.audio_capture.sys_queue.empty():
                sys_buffer = np.concatenate([sys_buffer, self.audio_capture.sys_queue.get_nowait()])

            while max(len(mic_buffer), len(sys_buffer)) >= chunk_samples:
                await self._enqueue(mic_buffer[:chunk_samples], sys_buffer[:chunk_samples])
                mic_buffer = mic_buffer[step_samples:]
                sys_buffer = sys_buffer[step_samples:]
                retained_overlap = overlap_samples

            if not self.running:
                # Não repete um resto contendo somente o overlap já processado.
                if max(len(mic_buffer), len(sys_buffer)) > retained_overlap:
                    await self._enqueue(mic_buffer, sys_buffer)
                await self._transcription_queue.put(None)
                return
            await asyncio.sleep(0.05)

    async def _enqueue(self, mic: np.ndarray, system: np.ndarray) -> None:
        mixed = AudioCapture.mix_and_normalize(mic, system)
        # Aguarda espaço em vez de descartar áudio quando o STT estiver ocupado.
        await self._transcription_queue.put(mixed)

    async def run_consumer(self) -> None:
        while True:
            audio_data = await self._transcription_queue.get()
            try:
                if audio_data is None:
                    return
                segments: list[TranscriptionSegment] = await asyncio.to_thread(
                    self.stt.transcribe, audio_data
                )
                if segments:
                    full_text = " ".join(s.text for s in segments)
                    deduped = deduplicate(self._last_text, full_text)
                    self._last_text = full_text
                    if deduped.strip():
                        start_str = self._fmt_time(segments[0].start)
                        end_str = self._fmt_time(segments[-1].end)
                        formatted = f"[{start_str} - {end_str}] {deduped}\n"
                        await asyncio.to_thread(self._save_line, formatted)
                        await self.session_events.put({"type": "transcription", "text": formatted})
            finally:
                self._transcription_queue.task_done()

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _save_line(self, text: str) -> None:
        # Erros de disco precisam impedir o resumo de uma transcrição incompleta.
        with open(self.output_file, "a", encoding="utf-8") as stream:
            stream.write(text)
