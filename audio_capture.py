import logging
import threading
import numpy as np
import pyaudiowpatch as pyaudio
from queue import Queue

logger = logging.getLogger(__name__)

class AudioCapture:
    def __init__(self, sample_rate=16000, mic_volume=1.0, sys_volume=1.0):
        self.sample_rate = sample_rate
        self.mic_volume = mic_volume
        self.sys_volume = sys_volume
        
        self.p = pyaudio.PyAudio()
        self.running = False
        
        # Filas para comunicação entre callbacks e a thread de processamento
        self.mic_queue = Queue()
        self.sys_queue = Queue()
        
        self.mic_stream = None
        self.sys_stream = None
        
        self.sys_channels = 2

    def get_wasapi_loopback(self):
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for loopback in self.p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    return loopback
            return default_speakers
        except OSError:
            logger.warning("WASAPI não encontrado. O áudio do sistema não será capturado.")
            return None

    def get_default_mic(self):
        try:
            return self.p.get_default_input_device_info()
        except OSError:
            logger.warning("Microfone não encontrado.")
            return None

    def _mic_callback(self, in_data, frame_count, time_info, status):
        if in_data and self.running:
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            self.mic_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def _sys_callback(self, in_data, frame_count, time_info, status):
        if in_data and self.running:
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            self.sys_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def start(self):
        self.running = True
        
        mic_info = self.get_default_mic()
        sys_info = self.get_wasapi_loopback()
        
        if mic_info:
            try:
                self.mic_stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=mic_info["index"],
                    stream_callback=self._mic_callback
                )
                self.mic_stream.start_stream()
                logger.info(f"Capturando microfone: {mic_info['name']}")
            except Exception as e:
                logger.error(f"Erro ao iniciar microfone: {e}")
                
        if sys_info:
            try:
                self.sys_channels = sys_info["maxInputChannels"]
                sys_rate = int(sys_info["defaultSampleRate"])
                
                # PyAudioWPatch loopback mode
                self.sys_stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=self.sys_channels,
                    rate=sys_rate,
                    input=True,
                    input_device_index=sys_info["index"],
                    stream_callback=self._sys_callback
                )
                self.sys_stream.start_stream()
                logger.info(f"Capturando áudio do sistema: {sys_info['name']}")
            except Exception as e:
                logger.error(f"Erro ao iniciar captura do sistema: {e}")

    def stop(self):
        self.running = False
        if self.mic_stream:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
        if self.sys_stream:
            self.sys_stream.stop_stream()
            self.sys_stream.close()
        self.p.terminate()

    @staticmethod
    def mix_and_normalize(mic_data, sys_data, mic_vol=1.0, sys_vol=1.0):
        """
        Mistura as amostras do microfone e do sistema e normaliza se passar de 1.0 ou -1.0.
        Garante que ambos tenham o mesmo tamanho preenchendo com zeros.
        """
        max_len = max(len(mic_data), len(sys_data))
        
        mic_padded = np.zeros(max_len, dtype=np.float32)
        sys_padded = np.zeros(max_len, dtype=np.float32)
        
        mic_padded[:len(mic_data)] = mic_data * mic_vol
        sys_padded[:len(sys_data)] = sys_data * sys_vol
        
        mixed = mic_padded + sys_padded
        
        # Normalização de pico para evitar clipping
        peak = np.max(np.abs(mixed))
        if peak > 1.0:
            mixed = mixed / peak
            
        return mixed

