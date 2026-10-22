"""Geração de atas em português usando Gemini."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from model_catalog import GeminiService

load_dotenv()

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


class GeminiSummarizer:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.environ.get(
            "GEMINI_DEFAULT_MODEL", "gemini-3.1-flash-lite"
        )
        self.service = GeminiService()

    async def get_available_models(self) -> list[str]:
        return [model.id for model in await self.service.list_models() if model.compatible]

    async def summarize(self, text: str) -> str:
        if not text.strip():
            raise ValueError("Nenhuma transcrição foi gerada para resumir.")
        return await self.service.generate(self.model_name, _build_prompt(text))


class SummarizerFactory:
    @staticmethod
    def get_summarizer(provider: str = "gemini", model_name: str | None = None) -> GeminiSummarizer:
        if provider != "gemini":
            raise ValueError("Provedor não suportado. Use Gemini.")
        return GeminiSummarizer(model_name)
