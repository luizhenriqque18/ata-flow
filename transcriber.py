import sys
import os
import site
import logging
from unittest.mock import MagicMock

# Injetar os diretórios do nvidia-cublas e cudnn (instalados via pip) no PATH do Windows
try:
    paths_to_add = []
    for site_pkg in site.getsitepackages():
        # Caminhos do nvidia-cublas e nvidia-cudnn
        for pkg in ["cublas", "cudnn"]:
            bin_path = os.path.join(site_pkg, "nvidia", pkg, "bin")
            if os.path.exists(bin_path):
                paths_to_add.append(bin_path)
        # Caminho do torch caso tenham instalado via pytorch
        torch_lib = os.path.join(site_pkg, "torch", "lib")
        if os.path.exists(torch_lib):
            paths_to_add.append(torch_lib)
            
    for p in paths_to_add:
        if p not in os.environ["PATH"]:
            os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]
except Exception:
    pass

# Workaround para Política de Controle de Aplicativo (Windows) que bloqueia a DLL do PyAV.
# Como passamos um numpy array diretamente pro modelo, não precisamos do 'av' para decodificar arquivos.
if 'av' not in sys.modules:
    sys.modules['av'] = MagicMock()

from faster_whisper import WhisperModel

# Verificar disponibilidade de CUDA usando ctranslate2 diretamente (sem depender do PyTorch)
try:
    import ctranslate2
    supported_cuda = ctranslate2.get_supported_compute_types("cuda")
    has_cuda = len(supported_cuda) > 0
except Exception:
    has_cuda = False

logger = logging.getLogger(__name__)

class LocalTranscriber:
    def __init__(self, model_size="small", language="pt"):
        self.model_size = model_size
        self.language = language
        self.model = None
        
        # Define o device e compute_type baseado na disponibilidade do CUDA
        if has_cuda:
            self.device = "cuda"
            self.compute_type = "float16"
            logger.info("CUDA disponível. Usando GPU (float16).")
        else:
            self.device = "cpu"
            self.compute_type = "int8"
            logger.info("CUDA indisponível ou PyTorch ausente. Fallback para CPU (int8).")

    def load_model(self):
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info(f"Modelo '{self.model_size}' carregado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar o modelo Whisper: {e}")
            return False

    def transcribe(self, audio_data):
        """
        Recebe numpy array (audio_data) em 16kHz float32.
        Retorna uma lista de dicts com 'start', 'end', 'text'.
        """
        if not self.model:
            raise RuntimeError("O modelo não foi carregado. Chame load_model() primeiro.")
            
        segments_result = []
        try:
            segments, info = self.model.transcribe(audio_data, language=self.language, beam_size=5)
            
            for segment in segments:
                segments_result.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
        except Exception as e:
            logger.error(f"Erro durante a transcrição: {e}")
            
        return segments_result

    @staticmethod
    def deduplicate(previous_text, current_text):
        """
        Deduplicação simples baseada no final do texto anterior e início do texto atual.
        Útil por causa da sobreposição de chunks.
        """
        if not previous_text or not current_text:
            return current_text
            
        # Pega as últimas 5 palavras do texto anterior
        prev_words = previous_text.split()[-5:]
        curr_words = current_text.split()
        
        if not prev_words or not curr_words:
            return current_text
            
        overlap_found = False
        match_idx = 0
        
        for i in range(len(prev_words)):
            prefix = prev_words[i:]
            if len(prefix) <= len(curr_words):
                if curr_words[:len(prefix)] == prefix:
                    overlap_found = True
                    match_idx = len(prefix)
                    break
                    
        if overlap_found:
            return " ".join(curr_words[match_idx:])
        
        return current_text

