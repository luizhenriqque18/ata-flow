"""Geração independente de TUI, sem chamadas reais ao Gemini."""

from argparse import Namespace
from unittest.mock import AsyncMock, Mock

import pytest

from ataflow.summaries.service import GenerateMeetingSummary


async def test_generates_summary_next_to_transcript(tmp_path):
    folder = tmp_path / "pasta.txt"
    folder.mkdir()
    source = folder / "reunião.txt"
    source.write_text("Decisão: lançar amanhã.", encoding="utf-8")
    generator = Mock(summarize=AsyncMock(return_value="# Ata\nLançar amanhã."))
    factory = Mock(return_value=generator)
    target = await GenerateMeetingSummary(factory).execute(source, "gemini", "modelo-escolhido")
    assert target == folder / "reunião-resumo.md"
    assert target.read_text(encoding="utf-8") == "# Ata\nLançar amanhã."
    assert source.read_text(encoding="utf-8") == "Decisão: lançar amanhã."
    factory.assert_called_once_with(provider="gemini", model_name="modelo-escolhido")
    generator.summarize.assert_awaited_once_with("Decisão: lançar amanhã.")


@pytest.mark.parametrize("failure", ["generation", "write", "empty"])
async def test_failure_preserves_transcript_and_previous_summary(tmp_path, monkeypatch, failure):
    source = tmp_path / "call.txt"
    source.write_text("Texto original", encoding="utf-8")
    target = tmp_path / "call-resumo.md"
    target.write_text("Ata anterior", encoding="utf-8")
    generator = Mock(summarize=AsyncMock(return_value="" if failure == "empty" else "Nova ata"))
    if failure == "generation":
        generator.summarize.side_effect = ConnectionError("Sem conexão")
    if failure == "write":
        monkeypatch.setattr(
            "ataflow.summaries.service.os.replace", Mock(side_effect=OSError("Sem espaço"))
        )
    with pytest.raises((ConnectionError, OSError, ValueError)):
        await GenerateMeetingSummary(lambda **_: generator).execute(source, "gemini", "modelo")
    assert source.read_text(encoding="utf-8") == "Texto original"
    assert target.read_text(encoding="utf-8") == "Ata anterior"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "name, content", [("missing.txt", None), ("empty.txt", " "), ("ata.md", "x")]
)
async def test_invalid_source_never_calls_provider(tmp_path, name, content):
    source = tmp_path / name
    if content is not None:
        source.write_text(content, encoding="utf-8")
    factory = Mock()
    with pytest.raises((ValueError, FileNotFoundError)):
        await GenerateMeetingSummary(factory).execute(source, "gemini", "modelo")
    factory.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
async def test_app_presents_service_result_or_error(tmp_path, monkeypatch, fails):
    from ataflow.cli import AtaFlowApp

    service = Mock(execute=AsyncMock(return_value=tmp_path / "call-resumo.md"))
    if fails:
        service.execute.side_effect = ValueError("Falha ao gerar ata")
    app = AtaFlowApp(Namespace(), {}, summary_service=service)
    notify = Mock()
    monkeypatch.setattr(app, "notify", notify)
    await app._generate_summary("call.txt", "gemini", "modelo")
    service.execute.assert_awaited_once_with("call.txt", "gemini", "modelo")
    assert notify.call_args.kwargs.get("severity") == ("error" if fails else None)
