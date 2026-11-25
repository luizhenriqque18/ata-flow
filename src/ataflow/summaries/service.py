"""Caso de uso de geração de atas, independente da interface de usuário."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ataflow.summaries.gemini import SummarizerFactory


class SummaryGenerator(Protocol):
    async def summarize(self, text: str) -> str: ...


class GenerateMeetingSummary:
    """Lê uma transcrição e publica a ata somente após geração e escrita completas."""

    def __init__(
        self,
        summarizer_factory: Callable[..., SummaryGenerator] = SummarizerFactory.get_summarizer,
    ) -> None:
        self.summarizer_factory = summarizer_factory

    async def execute(self, transcript: str | Path, provider: str, model: str) -> Path:
        source = Path(transcript)
        if source.suffix.lower() != ".txt":
            raise ValueError("Selecione um arquivo de transcrição .txt.")
        text = await asyncio.to_thread(source.read_text, encoding="utf-8")
        if not text.strip():
            raise ValueError("Nenhuma transcrição foi gerada para resumir.")
        generator = self.summarizer_factory(provider=provider, model_name=model)
        summary = await generator.summarize(text)
        if not summary.strip():
            raise ValueError("O modelo não retornou uma ata válida.")
        target = source.with_name(f"{source.stem}-resumo.md")
        await asyncio.to_thread(self._save, target, summary)
        return target

    @staticmethod
    def _save(target: Path, summary: str) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(summary)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
