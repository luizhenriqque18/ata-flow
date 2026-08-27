"""
Geradores de resumo LLM para transcricoes de reunioes.

Refatoracao em relacao ao original:
- Substituicao de urllib.request (bloqueante) por httpx.AsyncClient (async)
- Configuracao via variavel de ambiente (GEMINI_API_KEY) em vez de config.json
- Failover automatico mantido, mas totalmente asyncio-compativel
- SummarizerFactory permanece com a mesma interface publica
"""
from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_OLLAMA_BASE = "http://localhost:11434"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

_MEETING_PROMPT_TEMPLATE = """\
Voce e um assistente especialista em criar atas de reunioes corporativas.
Analise a transcricao bruta abaixo e produza um resumo profissional em Markdown.

Use linguagem formal, objetiva e concisa. Evite repeticoes.
A transcricao pode conter erros de reconhecimento de voz â€” interprete com bom senso.

Siga EXATAMENTE esta estrutura:

# Ata da Reuniao

## Resumo Geral
(Um paragrafo resumindo o contexto e objetivo principal)

## Principais Pontos Discutidos
- (Topico 1)

## Decisoes Tomadas
- (Decisao 1)

## Tarefas e Proximos Passos
- [Responsavel] â€” [Tarefa] â€” [Prazo, se mencionado]

## Questoes Pendentes
- (Duvidas sem resolucao)

REGRA: Responda SOMENTE em Portugues do Brasil.
REGRA: Nao invente nomes, prazos ou tarefas que nao estejam na transcricao.
REGRA: Se uma secao nao tiver informacao, escreva "Nenhum item identificado."
REGRA: Nao adicione texto fora da estrutura acima.

--- TRANSCRICAO ---
{text}
"""


def _build_prompt(text: str) -> str:
    return _MEETING_PROMPT_TEMPLATE.format(text=text)


# ======================================================================
# Ollama
# ======================================================================

class OllamaSummarizer:
    """Gera resumos usando um modelo Ollama rodando localmente."""

    def __init__(self, model_name: str = "llama3.2:1b") -> None:
        self.model_name = model_name

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{_OLLAMA_BASE}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def get_available_models() -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{_OLLAMA_BASE}/api/tags")
                if r.status_code == 200:
                    return [m.get("name") for m in r.json().get("models", [])]
        except Exception:
            pass
        return []

    async def summarize(self, text: str) -> str:
        if not text.strip():
            return "Nenhuma transcricao foi gerada para resumir."

        payload = {"model": self.model_name, "prompt": _build_prompt(text), "stream": False}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.info("Enviando transcricao para o Ollama...")
                r = await client.post(f"{_OLLAMA_BASE}/api/generate", json=payload)
                r.raise_for_status()
                return r.json().get("response", "Erro: Resposta vazia da IA.")
        except httpx.HTTPStatusError as exc:
            logger.error(f"Erro HTTP Ollama: {exc}")
            return f"Erro na API do Ollama: {exc.response.status_code}"
        except Exception as exc:
            logger.error(f"Erro ao chamar Ollama: {exc}")
            return f"Erro interno ao gerar o resumo: {exc}"


# ======================================================================
# Gemini
# ======================================================================

class GeminiSummarizer:
    """Gera resumos usando a API do Google Gemini."""

    def __init__(self, model_name: str = "gemini-3.1-flash-lite") -> None:
        self.model_name = model_name
        self.api_key: str = os.environ.get("GEMINI_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _url(self, model: str | None = None) -> str:
        m = model or self.model_name
        return f"{_GEMINI_BASE}/models/{m}:generateContent?key={self.api_key}"

    @staticmethod
    async def get_available_models(health_check: bool = False) -> list[str] | list[dict]:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{_GEMINI_BASE}/models?key={api_key}")
                r.raise_for_status()
                data = r.json()
                models = [
                    m["name"].replace("models/", "")
                    for m in data.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]

                if not health_check:
                    return models

                # Health check paralelo nos modelos flash/lite
                candidates = [m for m in models if "flash" in m or "pro" in m or "lite" in m]
                statuses = await GeminiSummarizer._run_health_check(candidates, api_key)
                return [{"name": m, "status": statuses.get(m, "[?]")} for m in candidates]
        except Exception as exc:
            logger.error(f"Erro ao buscar modelos Gemini: {exc}")
            return []

    @staticmethod
    async def _ping_model(client: httpx.AsyncClient, model: str, api_key: str) -> tuple[str, str]:
        url = f"{_GEMINI_BASE}/models/{model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "ping"}]}]}
        try:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                return model, "[OK]"
            return model, f"[FAIL] ({r.status_code})"
        except Exception:
            return model, "[TIMEOUT]"

    @staticmethod
    async def _run_health_check(models: list[str], api_key: str) -> dict[str, str]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = [GeminiSummarizer._ping_model(client, m, api_key) for m in models]
            import asyncio
            results = await asyncio.gather(*tasks, return_exceptions=True)
        return {m: s for r in results if isinstance(r, tuple) for m, s in [r]}

    async def verify_and_fallback(self) -> tuple[bool, str]:
        """Testa o modelo atual; faz failover para o proximo flash/lite se falhar."""
        api_key = self.api_key
        _, status = await self._ping_model(httpx.AsyncClient(timeout=5.0), self.model_name, api_key)
        if "[OK]" in status:
            return True, self.model_name

        logger.warning(f"Modelo {self.model_name} instavel ({status}). Iniciando failover...")
        all_models = await self.get_available_models(health_check=False)
        # Filtra candidatos mais confiaveis: nao pegar tts, omni, ou vision, prioriza lite/flash puro
        candidates = []
        for m in reversed(all_models):
            if ("flash" in m or "lite" in m) and "tts" not in m and "omni" not in m and "image" not in m and m != self.model_name:
                candidates.append(m)
        candidates = candidates[:3]
        if not candidates:
            return False, self.model_name

        statuses = await self._run_health_check(candidates, api_key)
        for cand in candidates:
            if "[OK]" in statuses.get(cand, ""):
                self.model_name = cand
                return True, cand

        return False, self.model_name

    async def summarize(self, text: str) -> str:
        if not text.strip():
            return "Nenhuma transcricao foi gerada para resumir."
        if not self.is_available():
            return "Erro: GEMINI_API_KEY nao configurada. Adicione ao arquivo .env."

        payload = {"contents": [{"parts": [{"text": _build_prompt(text)}]}]}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.info(f"Enviando transcricao para Gemini ({self.model_name})...")
                r = await client.post(self._url(), json=payload)
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return "Erro: Resposta inesperada do Gemini."
        except httpx.HTTPStatusError as exc:
            logger.error(f"Erro HTTP Gemini: {exc.response.status_code}")
            return f"Erro na API do Gemini: {exc.response.status_code}"
        except Exception as exc:
            logger.error(f"Erro ao chamar Gemini: {exc}")
            return f"Erro interno ao gerar resumo via Gemini: {exc}"


# ======================================================================
# Factory
# ======================================================================

class SummarizerFactory:
    @staticmethod
    def get_summarizer(provider: str, model_name: str | None = None) -> OllamaSummarizer | GeminiSummarizer:
        if provider == "gemini":
            model = model_name or os.environ.get("GEMINI_DEFAULT_MODEL", "gemini-3.1-flash-lite")
            return GeminiSummarizer(model_name=model)
        model = model_name or os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:1b")
        return OllamaSummarizer(model_name=model)
