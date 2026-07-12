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

    def summarize(self, text):
        if not text.strip():
            return "Nenhuma transcrição foi gerada para resumir."
            
        prompt = f"""Você é um assistente especialista em criar atas de reuniões corporativas.
Sua tarefa é analisar a transcrição bruta da reunião abaixo e produzir um resumo profissional em formato Markdown.

Siga EXATAMENTE esta estrutura:

# Ata da Reunião

## 📝 Resumo Geral
(Um parágrafo resumindo o contexto principal)

## 📌 Principais Pontos Discutidos
- (Tópico 1)
- (Tópico 2)

## 🎯 Decisões Tomadas
- (Decisão 1)

## 🛠️ Tarefas e Próximos Passos
- (Tarefa 1)

## ❓ Questões Pendentes ou Incertezas
- (Se houver alguma)

REGRA: Responda SOMENTE em Português do Brasil.
REGRA: Não invente nomes de pessoas, prazos ou tarefas que não estejam na transcrição. Se algo não foi discutido, deixe a categoria em branco.

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
