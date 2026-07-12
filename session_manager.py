import os
import time
import logging
import threading
import numpy as np
from queue import Queue, Empty
from datetime import datetime
from audio_capture import AudioCapture
from transcriber import LocalTranscriber

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, chunk_duration=10.0, overlap=2.0, max_queue_size=10):
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        
        self.audio_capture = AudioCapture()
        self.transcriber = LocalTranscriber()
        
        # Fila de chunks prontos para transcrição
        self.transcription_queue = Queue(maxsize=max_queue_size)
        
        self.running = False
        self.producer_thread = None
        self.consumer_thread = None
        
        self.output_dir = "./transcricoes"
        os.makedirs(self.output_dir, exist_ok=True)
        
        filename = datetime.now().strftime("%Y-%m-%d_%Hh%M-reuniao.txt")
        self.output_file = os.path.join(self.output_dir, filename)
        
        self.global_start_time = None
        self.last_text = ""
        
        self.session_events = Queue()

    def start(self):
        logger.info("Inicializando sessão...")
        if not self.transcriber.load_model():
            logger.error("Falha ao carregar modelo. Sessão não iniciada.")
            return False
            
        self.running = True
        self.global_start_time = time.time()
        
        self.audio_capture.start()
        
        self.producer_thread = threading.Thread(target=self._producer_loop, daemon=True)
        self.consumer_thread = threading.Thread(target=self._consumer_loop, daemon=True)
        
        self.producer_thread.start()
        self.consumer_thread.start()
        
        return True

    def _producer_loop(self):
        sample_rate = self.audio_capture.sample_rate
        chunk_samples = int(self.chunk_duration * sample_rate)
        overlap_samples = int(self.overlap * sample_rate)
        step_samples = chunk_samples - overlap_samples
        
        mic_buffer = np.array([], dtype=np.float32)
        sys_buffer = np.array([], dtype=np.float32)
        
        current_time_offset = 0.0
        
        while self.running:
            # Puxa tudo que tiver nas filas
            mic_new = []
            while not self.audio_capture.mic_queue.empty():
                mic_new.append(self.audio_capture.mic_queue.get())
                
            sys_new = []
            while not self.audio_capture.sys_queue.empty():
                sys_new.append(self.audio_capture.sys_queue.get())
                
            if mic_new:
                mic_buffer = np.concatenate([mic_buffer] + mic_new)
            if sys_new:
                sys_buffer = np.concatenate([sys_buffer] + sys_new)
                
            if len(mic_buffer) >= chunk_samples or len(sys_buffer) >= chunk_samples:
                mic_chunk = mic_buffer[:chunk_samples] if len(mic_buffer) > 0 else np.array([], dtype=np.float32)
                sys_chunk = sys_buffer[:chunk_samples] if len(sys_buffer) > 0 else np.array([], dtype=np.float32)
                
                # Diarização simples baseada na energia (RMS) de cada canal
                mic_rms = np.sqrt(np.mean(mic_chunk**2)) if len(mic_chunk) > 0 else 0.0
                sys_rms = np.sqrt(np.mean(sys_chunk**2)) if len(sys_chunk) > 0 else 0.0
                
                mic_active = mic_rms > 0.005
                sys_active = sys_rms > 0.005
                
                if mic_active and sys_active:
                    speaker_tag = "[Você + Outros]"
                elif mic_active:
                    speaker_tag = "[Você]"
                elif sys_active:
                    speaker_tag = "[Outros]"
                else:
                    speaker_tag = ""
                
                mixed = AudioCapture.mix_and_normalize(mic_chunk, sys_chunk)
                
                if len(mixed) < chunk_samples:
                    padded = np.zeros(chunk_samples, dtype=np.float32)
                    padded[:len(mixed)] = mixed
                    mixed = padded
                
                if self.transcription_queue.full():
                    logger.warning("Fila de transcrição cheia. Atraso identificado. Descartando chunk antigo.")
                    try:
                        self.transcription_queue.get_nowait()
                    except Empty:
                        pass
                
                self.transcription_queue.put({
                    "audio": mixed,
                    "offset": current_time_offset,
                    "speaker_tag": speaker_tag
                })
                
                current_time_offset += (step_samples / sample_rate)
                
                mic_buffer = mic_buffer[step_samples:]
                sys_buffer = sys_buffer[step_samples:]
                
            time.sleep(0.5)

    def _consumer_loop(self):
        while self.running or not self.transcription_queue.empty():
            try:
                item = self.transcription_queue.get(timeout=1.0)
                audio_data = item["audio"]
                offset = item["offset"]
                speaker_tag = item.get("speaker_tag", "")
                
                segments = self.transcriber.transcribe(audio_data)
                
                if segments:
                    full_text = " ".join([s["text"] for s in segments])
                    
                    deduped_text = self.transcriber.deduplicate(self.last_text, full_text)
                    self.last_text = deduped_text
                    
                    if deduped_text.strip():
                        start_time_str = self._format_time(offset)
                        end_time_str = self._format_time(offset + segments[-1]["end"])
                        
                        tag_str = f"{speaker_tag} " if speaker_tag else ""
                        formatted = f"[{start_time_str} - {end_time_str}] {tag_str}{deduped_text}\n"
                        self._save_to_file(formatted)
                        
                        self.session_events.put({
                            "type": "transcription",
                            "text": formatted
                        })
                        
                self.transcription_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Erro no consumer loop: {e}")

    def _format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _save_to_file(self, text):
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            logger.error(f"Erro ao salvar no arquivo: {e}")

    def stop(self):
        logger.info("Encerrando sessão (aguarde o processamento final)...")
        self.running = False
        
        self.audio_capture.stop()
        
        if self.producer_thread:
            self.producer_thread.join(timeout=5.0)
        if self.consumer_thread:
            # Espera até 10s para finalizar chunks pendentes
            self.consumer_thread.join(timeout=10.0)
            
        logger.info("Sessão finalizada com sucesso.")

