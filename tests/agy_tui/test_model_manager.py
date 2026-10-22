"""User flows for favorites, default model and Gemini selection."""

import asyncio
from argparse import Namespace

from textual.app import App
from textual.widgets import Button, DataTable, Input, Select, Static

from agy_tui.model_manager import ModelManagerScreen, ModelSelectionModal
from model_catalog import CheckResult, ModelInfo, ModelPreferences, PreferenceStore

MODELS = [
    ModelInfo("gemini-3.1-flash", "3.1", "Gemini", True),
    ModelInfo("gemini-2.5-pro", "2.5", "Gemini", True),
    ModelInfo("embedding", compatible=False),
]


class FakeService:
    async def list_models(self):
        return MODELS

    async def check(self, model):
        return CheckResult("Disponível", "2026-10-22", 20, 200)


class ScreenApp(App):
    def __init__(self, screen):
        super().__init__()
        self.target = screen
        self.result = None

    def on_mount(self):
        self.push_screen(self.target, self.closed)

    def closed(self, result):
        self.result = result


async def test_select_favorites_default_and_save(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    screen = ModelManagerScreen(store, FakeService())
    async with ScreenApp(screen).run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        assert screen.query_one("#catalog-table", DataTable).row_count == 3
        screen.selected_model = MODELS[0].id
        await pilot.click("#add-favorite")
        await pilot.pause(0.3)
        screen.selected_model = MODELS[1].id
        await pilot.click("#add-favorite")
        await pilot.pause(0.3)
        screen.selected_model = MODELS[1].id
        await pilot.click("#set-default")
        await pilot.click("#save-models")
        await pilot.pause()
        prefs = store.load()
        assert prefs.favorites == [MODELS[0].id, MODELS[1].id]
        assert prefs.default_model == MODELS[1].id


async def test_filters_and_cancel_does_not_save(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    screen = ModelManagerScreen(store, FakeService())
    async with ScreenApp(screen).run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        screen.query_one("#version-filter", Select).value = "3.1"
        await pilot.pause()
        assert screen.query_one("#catalog-table", DataTable).row_count == 1
        screen.query_one("#model-search", Input).value = "absent"
        await pilot.pause()
        assert screen.query_one("#catalog-table", DataTable).row_count == 0
        screen.selected_model = MODELS[0].id
        screen.add_favorite()
        await pilot.click("#cancel-models")
        assert not store.path.exists()


async def test_default_preselected_and_missing_default_not_replaced(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    prefs = ModelPreferences(configured=True, favorites=[MODELS[1].id], default_model=MODELS[1].id)
    store.save(prefs)
    for missing in (False, True):
        if missing:
            prefs.favorites.append("removed")
            prefs.default_model = "removed"
            store.save(prefs)
        screen = ModelSelectionModal(store=store, service=FakeService())
        async with ScreenApp(screen).run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            select = screen.query_one("#select-model", Select)
            if missing:
                assert not isinstance(select.value, str)
            else:
                assert select.value == MODELS[1].id
            assert screen.query_one("#btn-confirm", Button).disabled == missing


async def test_health_stops_on_quota_and_cancels(tmp_path):
    class LimitedService(FakeService):
        calls = []

        async def check(self, model):
            self.calls.append(model)
            return CheckResult("Limite/cota", "2026-10-22", 1, 429)

    service = LimitedService()
    screen = ModelManagerScreen(PreferenceStore(tmp_path / "models.json"), service)
    async with ScreenApp(screen).run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        await pilot.click("#test-all")
        await pilot.pause(0.3)
        assert service.calls == [MODELS[0].id]
        assert not screen.query_one("#test-all", Button).disabled

        async def slow_check(model):
            await asyncio.sleep(100)

        service.check = slow_check
        await pilot.click("#test-all")
        await pilot.pause()
        await pilot.click("#stop-tests")
        await pilot.pause()
        assert not screen.testing
        assert not screen.query_one("#test-all", Button).disabled


async def test_keyboard_selects_catalog_and_small_terminal_can_reach_actions(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    screen = ModelManagerScreen(store, FakeService())
    async with ScreenApp(screen).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#catalog-table", DataTable)
        table.focus()
        await pilot.press("down", "enter")
        await pilot.pause()
        assert screen.preferences.favorites == [MODELS[1].id]
        default_button = screen.query_one("#set-default", Button)
        default_button.scroll_visible(immediate=True)
        await pilot.pause()
        assert await pilot.click("#set-default")
        await pilot.click("#save-models")
        assert store.load().default_model == MODELS[1].id


async def test_manager_save_refreshes_modal_choices(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    modal = ModelSelectionModal(store=store, service=FakeService())
    app = ScreenApp(modal)
    async with app.run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        await pilot.click("#manage-models")
        await pilot.pause()
        manager = app.screen
        assert isinstance(manager, ModelManagerScreen)
        manager.selected_model = MODELS[1].id
        manager.add_favorite()
        await pilot.click("#save-models")
        await pilot.pause()
        assert app.screen is modal
        assert modal.query_one("#select-model", Select).value == MODELS[1].id
        await pilot.click("#btn-confirm")
        await pilot.pause()
        assert app.result == ("gemini", MODELS[1].id)


async def test_unavailable_catalog_preserves_cached_favorites(tmp_path):
    class OfflineService(FakeService):
        async def list_models(self):
            raise ConnectionError("offline")

    store = PreferenceStore(tmp_path / "models.json")
    prefs = ModelPreferences(
        configured=True, favorites=["removed"], default_model="removed", catalog=MODELS
    )
    store.save(prefs)
    screen = ModelManagerScreen(store, OfflineService())
    async with ScreenApp(screen).run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        assert screen.query_one("#catalog-table", DataTable).row_count == 3
        assert screen.query_one("#favorites-table", DataTable).row_count == 1
        assert "cache" in str(screen.query_one("#catalog-message", Static).render())
        assert screen.status("removed") == "Ausente do catálogo"
        await pilot.click("#cancel-models")
        assert store.load() == prefs


async def test_dashboard_opens_model_manager(tmp_path, monkeypatch):
    from main import AtaFlowApp

    store = PreferenceStore(tmp_path / "models.json")
    monkeypatch.setattr("main.ModelManagerScreen", lambda: ModelManagerScreen(store, FakeService()))
    app = AtaFlowApp(Namespace(provider="gemini"), {})
    async with app.run_test(size=(120, 42)) as pilot:
        await pilot.click("#btn-models")
        await pilot.pause()
        assert isinstance(app.screen, ModelManagerScreen)
        await pilot.click("#cancel-models")
        await pilot.pause()
        assert app.screen.query_one("#btn-models", Button)
