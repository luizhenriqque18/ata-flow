import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

class LocalSummarizer:
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
            
        prompt = f"""Você é um assistente especialista em criar atas de reuniões corporativas.
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
