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
            raise RuntimeError(f"Erro na API do Ollama: {exc.response.status_code}")
        except Exception as exc:
            logger.error(f"Erro ao chamar Ollama: {exc}")
            raise RuntimeError(f"Erro interno ao gerar o resumo: {exc}")


# ======================================================================
# Gemini
# ======================================================================
import asyncio
from google import genai
from google.genai.errors import APIError


class GeminiSummarizer:
    """Gera resumos usando a API do Google Gemini via httpx (async nativo)."""

    def __init__(self, model_name: str = "gemini-3.1-flash-lite") -> None:
        self.model_name = model_name
        self.api_key: str = os.environ.get("GEMINI_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _url(self, model: str | None = None) -> str:
        m = model or self.model_name
        return f"{_GEMINI_BASE}/models/{m}:generateContent?key={self.api_key}"

    @staticmethod
    def _extract_text(data: dict) -> str | None:
        """Extrai o texto da resposta JSON de forma segura."""
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return None

    async def get_available_models(self) -> list[str]:
        """Lista modelos usando o SDK google-genai (sincrono em thread)."""
        if not self.api_key:
            return []
        try:
            client = genai.Client(api_key=self.api_key)

            def fetch():
                return [
                    m.name.replace("models/", "")
                    for m in client.models.list()
                    if "generateContent" in getattr(m, "supported_actions", [])
                ]

            return await asyncio.to_thread(fetch)
        except Exception as exc:
            logger.error(f"Erro ao buscar modelos Gemini: {exc}")
            return []

    async def _ping_model(self, client: httpx.AsyncClient, model: str) -> tuple[str, str]:
        """Pinga um modelo via httpx para verificar disponibilidade."""
        try:
            r = await client.post(
                self._url(model),
                json={"contents": [{"parts": [{"text": "ping"}]}]},
            )
            if r.status_code == 200 and self._extract_text(r.json()):
                return model, "[OK]"
            return model, f"[FAIL] ({r.status_code})"
        except Exception:
            return model, "[TIMEOUT]"

    async def verify_and_fallback(self) -> tuple[bool, str]:
        """Testa o modelo atual; faz failover inteligente se falhar."""
        async with httpx.AsyncClient(timeout=8.0) as client:
            _, status = await self._ping_model(client, self.model_name)
            if "[OK]" in status:
                return True, self.model_name

            logger.warning(f"Modelo {self.model_name} instavel ({status}). Iniciando failover...")
            all_models = await self.get_available_models()

            candidates = [
                m for m in reversed(all_models)
                if ("flash" in m or "lite" in m)
                and "tts" not in m
                and "omni" not in m
                and "image" not in m
                and m != self.model_name
            ][:3]

            if not candidates:
                return False, self.model_name

            results = await asyncio.gather(
                *[self._ping_model(client, m) for m in candidates],
                return_exceptions=True,
            )
            statuses = {m: s for r in results if isinstance(r, tuple) for m, s in [r]}
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
                result = self._extract_text(r.json())
                if result is None:
                    finish = r.json().get("candidates", [{}])[0].get("finishReason", "UNKNOWN")
                    logger.error(f"Gemini sem texto. finish_reason={finish}")
                    return f"Erro: Gemini nao retornou texto (motivo: {finish})."
                return result
        except httpx.HTTPStatusError as exc:
            logger.error(f"Erro HTTP Gemini {exc.response.status_code}: {exc.response.text[:200]}")
            raise RuntimeError(f"Erro na API do Gemini: {exc.response.status_code}")
        except Exception as exc:
            logger.error(f"Erro ao chamar Gemini: {exc}")
            raise RuntimeError(f"Erro interno ao gerar resumo via Gemini: {exc}")


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
