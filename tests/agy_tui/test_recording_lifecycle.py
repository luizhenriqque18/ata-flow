"""A escolha do modelo só é liberada após a persistência da transcrição."""

import asyncio
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from textual.app import App

from agy_tui.screens import DeviceSelection
from main import AtaFlowApp, TranscriberScreen


@pytest.mark.parametrize("fails", [False, True])
async def test_stop_waits_before_returning_to_app(tmp_path, monkeypatch, fails):
    requested = asyncio.Event()
    release = asyncio.Event()
    output = tmp_path / "call.txt"

    async def finish():
        requested.set()
        await release.wait()
        if fails:
            raise OSError("Falha de escrita")
        output.write_text("Última fala salva", encoding="utf-8")
        return str(output)

    session = Mock(start=AsyncMock(return_value=True), finish=AsyncMock(side_effect=finish))
    session.finished = True
    session.session_events = asyncio.Queue()
    monkeypatch.setattr("main.SessionManager", Mock(return_value=session))
    monkeypatch.setattr("main.WhisperLocalSTT", Mock())
    screen = TranscriberScreen(
        Namespace(model="tiny", lang="pt", chunk=10, overlap=2),
        DeviceSelection(0, "Mic", 1, "Sistema"),
    )
    results = []

    class RecordingApp(App):
        def on_mount(self):
            self.push_screen(screen, results.append)

    async with RecordingApp().run_test() as pilot:
        stopping = asyncio.create_task(screen.action_stop_session())
        await asyncio.wait_for(requested.wait(), 2)
        assert not results
        assert not output.exists()
        release.set()
        await stopping
        await pilot.pause()
        if fails:
            assert results == [None]
        else:
            assert results == [str(output)]
            assert Path(results[0]).read_text(encoding="utf-8") == "Última fala salva"


async def test_quit_finishes_recording_before_exit(monkeypatch):
    session = Mock(finish=AsyncMock())
    screen = object.__new__(TranscriberScreen)
    screen.session = session
    app = AtaFlowApp(Namespace(), {})
    # A pilha expõe a gravação ativa mesmo que outra tela esteja sobre ela.
    monkeypatch.setattr(type(app), "screen_stack", property(lambda _: [screen]))
    exit_mock = Mock()
    monkeypatch.setattr(app, "exit", exit_mock)
    await app.action_quit()
    session.finish.assert_awaited_once()
    exit_mock.assert_called_once()
