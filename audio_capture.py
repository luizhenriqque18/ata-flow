"""
Captura de audio do microfone e do sistema (WASAPI loopback) no Windows.

Refatoracao em relacao ao original:
- Filas de saida sao agora asyncio.Queue (thread-safe com loop.call_soon_threadsafe)
- A API publica permanece a mesma: start() / stop() / list_devices()
- Sem mudancas no comportamento de downmix e resample
"""
from __future__ import annotations

import asyncio
import logging

import numpy as np
import pyaudiowpatch as pyaudio

logger = logging.getLogger(__name__)


class AudioCapture:
    """
    Captura audio de microfone e loopback do sistema simultaneamente.

    Cada canal possui uma asyncio.Queue propria que pode ser consumida
    diretamente pelo event loop do Textual sem polling em thread separada.
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        mic_volume: float = 1.0,
        sys_volume: float = 1.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.mic_volume = mic_volume
        self.sys_volume = sys_volume

        self._pa = pyaudio.PyAudio()
        self.running = False

        # Filas asyncio â€” consumidas pelo SessionManager no event loop
        self.mic_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self.sys_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

        self._mic_stream: object | None = None
        self._sys_stream: object | None = None
        self._sys_channels: int = 2
        self._sys_rate: int = sample_rate
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Descoberta de dispositivos
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> dict[str, list[dict]]:
        """Lista microfones e dispositivos de loopback disponiveis."""
        pa = pyaudio.PyAudio()
        mics: list[dict] = []
        loopbacks: list[dict] = []

        try:
            for i in range(pa.get_device_count()):
                dev = pa.get_device_info_by_index(i)
                if dev.get("maxInputChannels", 0) > 0:
                    if dev.get("isLoopbackDevice", False):
                        loopbacks.append(dict(dev))
                    else:
                        mics.append(dict(dev))
        except Exception as exc:
            logger.error(f"Erro ao listar dispositivos: {exc}")
        finally:
            pa.terminate()

        return {"mics": mics, "loopbacks": loopbacks}

    def _get_wasapi_loopback(self) -> dict | None:
        """Retorna o dispositivo de loopback WASAPI do output padrao."""
        try:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self._pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for loopback in self._pa.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    return dict(loopback)
            return dict(default_speakers)
        except OSError:
            logger.warning("WASAPI nao encontrado. Audio do sistema nao sera capturado.")
            return None

    def _get_default_mic(self) -> dict | None:
        """Retorna o microfone padrao do sistema."""
        try:
            return dict(self._pa.get_default_input_device_info())
        except OSError:
            logger.warning("Microfone nao encontrado.")
            return None

    # ------------------------------------------------------------------
    # Callbacks de audio (chamados em threads do PyAudio)
    # ------------------------------------------------------------------

    def _put_async(self, queue: asyncio.Queue, data: np.ndarray) -> None:
        """Despacha dado para uma asyncio.Queue de forma thread-safe."""
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(queue.put_nowait, data)
            except asyncio.QueueFull:
                logger.debug("Fila de audio cheia, descartando chunk.")

    def _mic_callback(self, in_data: bytes, _frame_count: int, _time_info: dict, _status: int) -> tuple:
        if in_data and self.running:
            audio = np.frombuffer(in_data, dtype=np.float32)
            self._put_async(self.mic_queue, audio)
        return (in_data, pyaudio.paContinue)

    def _sys_callback(self, in_data: bytes, _frame_count: int, _time_info: dict, _status: int) -> tuple:
        if in_data and self.running:
            audio = np.frombuffer(in_data, dtype=np.float32)

            if self._sys_channels > 1:
                audio = audio.reshape(-1, self._sys_channels).mean(axis=1).astype(np.float32)

            if self._sys_rate != self.sample_rate:
                n = int(len(audio) * self.sample_rate / self._sys_rate)
                xp = np.arange(len(audio))
                xq = np.linspace(0, len(audio) - 1, num=n)
                audio = np.interp(xq, xp, audio).astype(np.float32)

            self._put_async(self.sys_queue, audio)
        return (in_data, pyaudio.paContinue)

    # ------------------------------------------------------------------
    # Controle de ciclo de vida
    # ------------------------------------------------------------------

    def start(self, mic_index: int | None = None, sys_index: int | None = None, loop: "asyncio.AbstractEventLoop | None" = None) -> None:
        """Inicia a captura de audio. Deve ser chamado com o event loop ativo."""
        self._loop = loop or asyncio.get_event_loop()
        self.running = True

        mic_info = (
            self._pa.get_device_info_by_index(mic_index) if mic_index is not None
            else self._get_default_mic()
        )
        sys_info = (
            self._pa.get_device_info_by_index(sys_index) if sys_index is not None
            else self._get_wasapi_loopback()
        )

        if mic_info:
            try:
                self._mic_stream = self._pa.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=mic_info["index"],
                    stream_callback=self._mic_callback,
                )
                self._mic_stream.start_stream()
                logger.info(f"Microfone: {mic_info['name']}")
            except Exception as exc:
                logger.error(f"Erro ao iniciar microfone: {exc}")

        if sys_info:
            try:
                self._sys_channels = sys_info["maxInputChannels"]
                self._sys_rate = int(sys_info["defaultSampleRate"])
                self._sys_stream = self._pa.open(
                    format=pyaudio.paFloat32,
                    channels=self._sys_channels,
                    rate=self._sys_rate,
                    input=True,
                    input_device_index=sys_info["index"],
                    stream_callback=self._sys_callback,
                )
                self._sys_stream.start_stream()
                logger.info(f"Audio do sistema: {sys_info['name']}")
            except Exception as exc:
                logger.error(f"Erro ao iniciar audio do sistema: {exc}")

    def stop(self) -> None:
        """Para a captura e libera todos os recursos do PyAudio."""
        self.running = False
        for stream in (self._mic_stream, self._sys_stream):
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
        try:
            self._pa.terminate()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Utilitario de mixagem
    # ------------------------------------------------------------------

    @staticmethod
    def mix_and_normalize(
        mic_data: np.ndarray,
        sys_data: np.ndarray,
        mic_vol: float = 1.0,
        sys_vol: float = 1.0,
    ) -> np.ndarray:
        """
        Mistura mic e sistema, normaliza para evitar clipping.

        Preenche com zeros o canal mais curto antes de somar.
        """
        max_len = max(len(mic_data), len(sys_data))
        mic_p = np.zeros(max_len, dtype=np.float32)
        sys_p = np.zeros(max_len, dtype=np.float32)
        mic_p[: len(mic_data)] = mic_data * mic_vol
        sys_p[: len(sys_data)] = sys_data * sys_vol

        mixed = mic_p + sys_p
        peak = np.max(np.abs(mixed))
        if peak > 1.0:
            mixed /= peak

        return mixed
