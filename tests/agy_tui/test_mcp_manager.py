from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Collapsible, Input, Select, Static, Switch, TextArea

from agy_tui.mcp_manager import MCPManagerScreen
from mcp_network import MCPHTTPService
from mcp_settings import MCPSettingsStore


class SettingsApp(App):
    def __init__(self, store):
        super().__init__()
        self.store = store

    async def on_mount(self):
        await self.push_screen(MCPManagerScreen(self.store))


@pytest.mark.asyncio
async def test_save_enable_and_disable(tmp_path):
    (tmp_path / "transcricoes").mkdir()
    store = MCPSettingsStore(tmp_path / "prefs.json")
    app = SettingsApp(store)
    async with app.run_test(size=(100, 55)) as pilot:
        await pilot.pause()
        assert not app.screen.query_one(Switch).value
        assert "[mcp_servers.ataflow]" in app.screen.query_one(TextArea).text
        app.screen.query_one(Select).value = "json"
        await pilot.pause()
        assert '"mcpServers"' in app.screen.query_one(TextArea).text
        app.screen.query_one(Switch).value = True
        app.screen.query_one("#mcp-results", Input).value = "8"
        await pilot.click("#mcp-save")
        assert store.load().enabled
        assert store.load().max_results == 8
        app.push_screen(MCPManagerScreen(store))
        await pilot.pause()
        app.screen.query_one(Switch).value = False
        await pilot.click("#mcp-save")
        assert not store.load().enabled


@pytest.mark.asyncio
async def test_invalid_and_cancel_preserve_preferences(tmp_path):
    store = MCPSettingsStore(tmp_path / "prefs.json")
    app = SettingsApp(store)
    async with app.run_test(size=(100, 55)) as pilot:
        await pilot.pause()
        app.screen.query_one("#mcp-results", Input).value = "0"
        await pilot.click("#mcp-save")
        assert isinstance(app.screen, MCPManagerScreen)
        assert not store.path.exists()
        app.screen.query_one(Switch).value = True
        await pilot.press("escape")
        assert not store.path.exists()


@pytest.mark.asyncio
async def test_dashboard_opens_mcp_settings(tmp_path, monkeypatch):
    from argparse import Namespace

    import main

    store = MCPSettingsStore(tmp_path / "prefs.json")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "MCPManagerScreen", lambda: MCPManagerScreen(store))
    app = main.AtaFlowApp(Namespace(), {})
    app.mcp_http_service = MCPHTTPService(store)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#btn-mcp")
        await pilot.pause()
        assert isinstance(app.screen, MCPManagerScreen)
        await pilot.press("escape")
        assert not store.path.exists()


@pytest.mark.asyncio
async def test_network_controls_save_and_report_start_error(tmp_path):
    class FakeService:
        running = False
        calls = 0

        async def apply(self):
            self.calls += 1
            raise OSError("Porta em uso")

    (tmp_path / "transcricoes").mkdir()
    store = MCPSettingsStore(tmp_path / "prefs.json")
    app = SettingsApp(store)
    app.mcp_http_service = FakeService()
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(Collapsible).collapsed = False
        screen.query_one("#mcp-enabled", Switch).value = True
        screen.query_one("#mcp-network-enabled", Switch).value = True
        screen.query_one("#mcp-host", Input).value = "0.0.0.0"
        screen.query_one("#mcp-public-host", Input).value = "192.168.1.10"
        screen.query_one("#mcp-generate-token", Button).press()
        await pilot.pause()
        token = screen.query_one("#mcp-token", Input).value
        assert len(token) >= 32
        assert screen.query_one("#mcp-token", Input).password
        screen.query_one("#mcp-save", Button).scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#mcp-save")
        await pilot.pause()
        assert store.load().http_token == token
        assert store.load().network_enabled
        assert app.mcp_http_service.calls == 1
        assert "Porta em uso" in str(screen.query_one("#mcp-error", Static).render())
        assert isinstance(app.screen, MCPManagerScreen)
        screen.query_one("#mcp-format", Select).value = "http-codex"
        await pilot.pause()
        assert "192.168.1.10:8765/mcp" in screen.query_one(TextArea).text
        assert token not in screen.query_one(TextArea).text
