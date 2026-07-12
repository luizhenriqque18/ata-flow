import json
import logging
import urllib.request
import urllib.error
from config import get_gemini_key

logger = logging.getLogger(__name__)

class OllamaSummarizer:
    def __init__(self, model_name="llama3.2:1b", api_url="http://localhost:11434/api/generate"):
        self.model_name = model_name
        self.api_url = api_url

    def is_available(self):
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as response:
                return response.status == 200
        except Exception:
            return False

    @staticmethod
    def get_available_models():
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return [m.get("name") for m in data.get("models", [])]
                return []
        except Exception:
            return []

    def summarize(self, text):
        if not text.strip():
            return "Nenhuma transcrição foi gerada para resumir."
            
        prompt = self._get_prompt(text)
        
        data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        req = urllib.request.Request(
            self.api_url, 
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            logger.info("Enviando transcrição para o Ollama (isso pode levar alguns segundos)...")
            with urllib.request.urlopen(req, timeout=120.0) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    return result.get("response", "Erro: Resposta vazia da IA.")
                else:
                    return f"Erro na API do Ollama: {response.status}"
        except Exception as e:
            logger.error(f"Erro ao chamar Ollama: {e}")
            return f"Erro interno ao tentar gerar o resumo: {e}"

    def _get_prompt(self, text):
        return f"""Você é um assistente especialista em criar atas de reuniões corporativas.
Sua tarefa é analisar a transcrição bruta da reunião abaixo e produzir um resumo profissional em formato Markdown.

Use linguagem formal, objetiva e concisa. Evite repetições e paráfrases longas.
A transcrição pode conter erros de reconhecimento de voz — interprete com bom senso, mas não corrija nomes próprios sem certeza.

Siga EXATAMENTE esta estrutura:

# Ata da Reunião

## 📝 Resumo Geral
(Um parágrafo resumindo o contexto e objetivo principal da reunião)

## 📌 Principais Pontos Discutidos
- (Tópico 1)
- (Tópico 2)

## 🎯 Decisões Tomadas
- (Decisão 1)

## 🛠️ Tarefas e Próximos Passos
- [Responsável] — [Tarefa] — [Prazo, se mencionado]

## ❓ Questões Pendentes ou Incertezas
- (Dúvidas ou pontos que ficaram sem resolução)

REGRA: Responda SOMENTE em Português do Brasil.
REGRA: Não invente nomes, prazos ou tarefas que não estejam explicitamente na transcrição.
REGRA: Se uma seção não tiver informação relevante, escreva "Nenhum item identificado."
REGRA: Não adicione comentários, explicações ou texto fora da estrutura acima.

--- TRANSCRIÇÃO ---
{text}
"""

class GeminiSummarizer:
    def __init__(self, model_name="gemini-2.0-flash"):
        self.model_name = model_name
        self.api_key = get_gemini_key()
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def is_available(self):
        return bool(self.api_key)

    @staticmethod
    def get_available_models():
        api_key = get_gemini_key()
        if not api_key:
            return []
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return [m.get("name").replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
                return []
        except Exception as e:
            logger.error(f"Erro ao buscar modelos do Gemini: {e}")
            return []

    def summarize(self, text):
        if not text.strip():
            return "Nenhuma transcrição foi gerada para resumir."
            
        if not self.is_available():
            return "Erro: Chave da API do Gemini não configurada. Use --set-gemini-key para configurar."
            
        prompt = OllamaSummarizer()._get_prompt(text)
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        req = urllib.request.Request(
            self.api_url, 
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            logger.info(f"Enviando transcrição para o Gemini ({self.model_name})...")
            with urllib.request.urlopen(req, timeout=120.0) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    try:
                        return result["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError):
                        return "Erro: Resposta inesperada do Gemini."
                else:
                    return f"Erro na API do Gemini: {response.status}"
        except urllib.error.HTTPError as e:
             logger.error(f"Erro HTTP do Gemini: {e.code} - {e.reason}")
             try:
                 err_body = e.read().decode('utf-8')
                 logger.error(f"Detalhes do erro: {err_body}")
             except:
                 pass
             return f"Erro na API do Gemini: {e.code}"
        except Exception as e:
            logger.error(f"Erro ao chamar Gemini: {e}")
            return f"Erro interno ao tentar gerar o resumo via Gemini: {e}"

class SummarizerFactory:
    @staticmethod
    def get_summarizer(provider, model_name=None):
        if provider == "gemini":
            if model_name is None or model_name == "llama3.2:1b":
                model_name = "gemini-2.0-flash"
            return GeminiSummarizer(model_name=model_name)
        else: # ollama
            if model_name is None:
                model_name = "llama3.2:1b"
            return OllamaSummarizer(model_name=model_name)
