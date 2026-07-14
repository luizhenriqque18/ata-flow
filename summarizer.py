import json
import logging
import urllib.request
import urllib.error
import concurrent.futures
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
    def __init__(self, model_name="gemini-3.5-flash"):
        self.model_name = model_name
        self.api_key = get_gemini_key()
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def is_available(self):
        return bool(self.api_key)

    @staticmethod
    def get_available_models(health_check=False):
        api_key = get_gemini_key()
        if not api_key:
            return []
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    models = [m.get("name").replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
                    
                    if health_check:
                        # Filter to standard textual models to avoid rate limiting
                        test_models = [m for m in models if "flash" in m or "pro" in m or "lite" in m]
                        statuses = GeminiSummarizer.run_health_check(test_models)
                        return [{"name": m, "status": statuses.get(m, "[?] Desconhecido")} for m in test_models]
                    return models
                return []
        except Exception as e:
            logger.error(f"Erro ao buscar modelos do Gemini: {e}")
            return []

    @staticmethod
    def ping_model(model_name):
        """Dispara um micro-prompt para verificar a saude do modelo."""
        api_key = get_gemini_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        data = {"contents": [{"parts": [{"text": "ping"}]}]}
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=5.0) as response:
                if response.status == 200:
                    return model_name, "[OK]"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return model_name, "[OFF] (404 - Nao Encontrado)"
            elif e.code == 429:
                return model_name, "[LIMIT] (429 - Gargalo/Too Many Requests)"
            elif e.code == 503:
                return model_name, "[DOWN] (503 - Servico Indisponivel)"
            else:
                return model_name, f"[FAIL] (Erro {e.code})"
        except Exception:
            return model_name, "[TIMEOUT] (Falha de Conexao)"
            
        return model_name, "[FAIL] (Erro Desconhecido)"

    @staticmethod
    def run_health_check(models):
        """Testa múltiplos modelos simultaneamente."""
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(GeminiSummarizer.ping_model, m) for m in models]
            for future in concurrent.futures.as_completed(futures):
                model_name, status = future.result()
                results[model_name] = status
        return results

    def verify_and_fallback(self):
        """Testa o modelo atual. Se falhar, busca o próximo modelo flash/lite disponível."""
        _, status = self.ping_model(self.model_name)
        if "[OK]" in status:
            return True, self.model_name
            
        logger.warning(f"Modelo {self.model_name} instável ({status}). Iniciando Failover automático...")
        
        # Obter modelos (sem health_check detalhado ainda para economizar tempo)
        all_models = self.get_available_models(health_check=False)
        fallback_candidates = [m for m in all_models if ("flash" in m or "lite" in m) and m != self.model_name]
        
        # Testar apenas os 3 primeiros candidatos para ser ultra rápido
        candidates = fallback_candidates[:3]
        if not candidates:
            return False, self.model_name
            
        statuses = self.run_health_check(candidates)
        for cand in candidates:
            if "[OK]" in statuses.get(cand, ""):
                logger.info(f"Failover bem-sucedido: Trocando para {cand}")
                self.model_name = cand
                self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
                return True, cand
                
        return False, self.model_name

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
                model_name = "gemini-3.5-flash"
            return GeminiSummarizer(model_name=model_name)
        else: # ollama
            if model_name is None:
                model_name = "llama3.2:1b"
            return OllamaSummarizer(model_name=model_name)
