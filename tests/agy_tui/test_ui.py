"""
Testes dos componentes de UI da agy_tui.

Usa o framework de testes nativo do Textual (pilot) para garantir
que os widgets reagem corretamente a dados sem precisar de hardware.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from agy_tui.components import ServiceStatusBar, TranscriptionLog


# App minima apenas para hospedar o widget em testes
class _TestApp(App[None]):
    def __init__(self, widget_class, **kwargs) -> None:
        super().__init__()
        self._widget_class = widget_class
        self._kwargs = kwargs

    def compose(self) -> ComposeResult:
        yield self._widget_class(**self._kwargs)


@pytest.mark.asyncio
async def test_transcription_log_adds_line() -> None:
    """TranscriptionLog deve adicionar linhas sem lancar excecoes."""
    async with _TestApp(TranscriptionLog).run_test() as pilot:
        log = pilot.app.query_one(TranscriptionLog)
        # Nao deve levantar excecao
        log.add_transcription("Bom dia a todos", speaker_tag="[Voce]")
        log.add_transcription("Ola, boa tarde")


@pytest.mark.asyncio
async def test_service_status_bar_updates() -> None:
    """ServiceStatusBar deve atualizar seus estados reativos corretamente."""
    async with _TestApp(ServiceStatusBar).run_test() as pilot:
        bar = pilot.app.query_one(ServiceStatusBar)

        bar.update_whisper("carregado")
        bar.update_audio("capturando")
        bar.update_llm("gerando")

        assert bar.whisper_status == "carregado"
        assert bar.audio_status == "capturando"
        assert bar.llm_status == "gerando"


@pytest.mark.asyncio
async def test_service_status_bar_default_values() -> None:
    """ServiceStatusBar deve ter valores padrao corretos ao ser criado."""
    async with _TestApp(ServiceStatusBar).run_test() as pilot:
        bar = pilot.app.query_one(ServiceStatusBar)
        assert bar.whisper_status == "descarregado"
        assert bar.audio_status == "parado"
        assert bar.llm_status == "inativo"
