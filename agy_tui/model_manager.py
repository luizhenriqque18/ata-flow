"""Gemini model selection and personal catalog screens."""

from __future__ import annotations

import os
from copy import deepcopy

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static

from model_catalog import GeminiService, ModelInfo, PreferenceStore


class ModelManagerScreen(Screen[bool]):
    """Edit a draft; only Save commits preferences and cached checks."""

    TITLE = "Gerenciar modelos — Gemini"
    BINDINGS = [Binding("escape", "cancel", "Voltar")]
    DEFAULT_CSS = """
    ModelManagerScreen .filters { height: 3; }
    ModelManagerScreen Input { width: 2fr; }
    ModelManagerScreen Select { width: 1fr; }
    #manager-content { height: 1fr; padding: 0 1; }
    #model-panes { height: 1fr; min-height: 16; }
    #catalog-pane, #favorites-pane { width: 1fr; padding: 0 1; }
    #catalog-table, #favorites-table { height: 1fr; min-height: 5; }
    #model-details { height: 7; overflow-y: auto; }
    ModelManagerScreen .actions { height: auto; min-height: 3; }
    ModelManagerScreen .actions Button { min-width: 10; width: 1fr; }
    #refresh-catalog, #set-default, #test-all, #stop-tests { margin-left: 1; }
    #manager-footer {
        height: 5; padding: 1; align: right middle;
        background: $surface-darken-1;
    }
    #manager-footer Button { width: auto; min-width: 14; margin-left: 1; }
    #catalog-message { height: auto; max-height: 3; }
    #check-progress { height: auto; max-height: 2; }
    #test-warning { height: auto; color: $warning; }
    """

    def __init__(
        self, store: PreferenceStore | None = None, service: GeminiService | None = None
    ) -> None:
        super().__init__()
        self.store = store or PreferenceStore()
        self.service = service or GeminiService()
        self.preferences = deepcopy(self.store.load())
        self.models = {model.id: model for model in self.preferences.catalog}
        self.selected_model: str | None = None
        self.testing: set[str] = set()
        self.testing_worker = None
        self.loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="manager-content"):
            yield Static(
                "Provedor: Gemini | Favoritos e padrão são salvos apenas ao clicar Salvar."
            )
            with Horizontal(classes="filters"):
                yield Input(placeholder="Buscar modelo...", id="model-search")
                yield Select(
                    [("Todas as versões", "all")],
                    value="all",
                    allow_blank=False,
                    id="version-filter",
                )
                yield Select(
                    [
                        (value, value)
                        for value in (
                            "Todos",
                            "Disponível",
                            "Com erro",
                            "Não testado",
                            "Incompatível",
                        )
                    ],
                    value="Todos",
                    allow_blank=False,
                    id="status-filter",
                )
            yield Static("Carregando catálogo...", id="catalog-message", markup=False)
            with Horizontal(id="model-panes"):
                with Vertical(id="catalog-pane"):
                    yield Label("Catálogo do Gemini (Enter: adicionar)")
                    yield DataTable(id="catalog-table", cursor_type="row", zebra_stripes=True)
                    with Horizontal(classes="actions"):
                        yield Button("Adicionar →", id="add-favorite", variant="primary")
                        yield Button("Atualizar", id="refresh-catalog")
                with Vertical(id="favorites-pane"):
                    yield Label("Meus modelos — ★ padrão")
                    yield DataTable(id="favorites-table", cursor_type="row", zebra_stripes=True)
                    with VerticalScroll(id="model-details"):
                        yield Static(
                            "Selecione um modelo para ver os detalhes.",
                            id="model-detail-text",
                            markup=False,
                        )
                    with Horizontal(classes="actions"):
                        yield Button("Remover", id="remove-favorite")
                        yield Button("Definir padrão", id="set-default", variant="primary")
            yield Static(
                "Os testes fazem chamadas ao Gemini e podem consumir cota.", id="test-warning"
            )
            yield Static("Nenhum teste em andamento.", id="check-progress", markup=False)
            with Horizontal(classes="actions"):
                yield Button("Testar selecionado", id="test-one")
                yield Button("Testar todos", id="test-all")
                yield Button("Parar testes", id="stop-tests", disabled=True)
        with Horizontal(id="manager-footer"):
            yield Button("Cancelar", id="cancel-models")
            yield Button("Salvar", id="save-models", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#catalog-table", DataTable).add_columns("Modelo", "Versão", "Último teste")
        self.query_one("#favorites-table", DataTable).add_columns("Modelo", "Último teste")
        self.refresh_tables()
        self.run_worker(self.load_catalog(), group="catalog", exclusive=True)

    async def load_catalog(self) -> None:
        self.loading = True
        self.query_one("#refresh-catalog", Button).disabled = True
        try:
            models = await self.service.list_models()
            self.models = {model.id: model for model in models}
            self.preferences.catalog = models
            versions = sorted({model.version for model in models})
            selector = self.query_one("#version-filter", Select)
            selector.set_options([("Todas as versões", "all")] + [(v, v) for v in versions])
            selector.value = "all"
            self.query_one("#catalog-message", Static).update(
                f"{len(models)} modelos. Disponível = respondeu no último teste; "
                "não é garantia futura."
            )
        except Exception:
            self.query_one("#catalog-message", Static).update(
                "Falha ao consultar catálogo. Exibindo cache, se disponível. "
                "Verifique conexão e GEMINI_API_KEY."
            )
        finally:
            self.loading = False
            self.query_one("#refresh-catalog", Button).disabled = False
            self.refresh_tables()

    def status(self, model_id: str) -> str:
        if model_id not in self.models:
            return "Ausente do catálogo"
        if not self.models[model_id].compatible:
            return "Incompatível"
        if model_id in self.testing:
            return "Testando"
        result = self.preferences.checks.get(model_id)
        if not result:
            return "Não testado"
        suffix = f" ({result.http_code})" if result.http_code else ""
        return result.status + suffix

    def refresh_tables(self) -> None:
        catalog = self.query_one("#catalog-table", DataTable)
        favorites = self.query_one("#favorites-table", DataTable)
        search = self.query_one("#model-search", Input).value.casefold()
        version = self.query_one("#version-filter", Select).value
        status_filter = self.query_one("#status-filter", Select).value
        # Keep keyboard position stable while background test results arrive.
        for table in (catalog, favorites):
            table.clear()
        for model in self.models.values():
            status = self.status(model.id)
            if search not in model.id.casefold() or version not in ("all", model.version):
                continue
            if status_filter == "Disponível" and not status.startswith("Disponível"):
                continue
            if status_filter == "Com erro" and (
                model.id not in self.preferences.checks
                or self.preferences.checks[model.id].status == "Disponível"
            ):
                continue
            if status_filter in ("Não testado", "Incompatível") and status != status_filter:
                continue
            catalog.add_row(model.id, model.version, status, key=model.id)
        for model_id in self.preferences.favorites:
            star = "★ " if model_id == self.preferences.default_model else ""
            favorites.add_row(star + model_id, self.status(model_id), key=model_id)
        for table in (catalog, favorites):
            if self.selected_model in table.rows:
                table.move_cursor(row=table.get_row_index(self.selected_model))
        self.show_details()

    def show_details(self) -> None:
        if not self.selected_model:
            return
        model = self.models.get(self.selected_model)
        result = self.preferences.checks.get(self.selected_model)
        lines = [self.selected_model, self.status(self.selected_model)]
        if model:
            lines.append(f"Família: {model.family} | Versão: {model.version}")
        if result:
            lines += [
                f"Último teste (UTC): {result.checked_at}",
                f"Duração: {result.duration_ms} ms | HTTP: {result.http_code or '—'}",
                result.detail,
            ]
        self.query_one("#model-detail-text", Static).update("\n".join(lines))

    @on(Input.Changed, "#model-search")
    @on(Select.Changed, "#version-filter")
    @on(Select.Changed, "#status-filter")
    def filters_changed(self) -> None:
        if self.is_mounted:
            self.refresh_tables()

    @on(DataTable.RowHighlighted)
    def highlight_model(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.has_focus:
            self.selected_model = str(event.row_key.value)
            self.show_details()

    @on(DataTable.RowSelected, "#catalog-table")
    def catalog_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_model = str(event.row_key.value)
        self.add_favorite()

    def add_favorite(self) -> None:
        model = self.models.get(self.selected_model or "")
        if not model or not model.compatible:
            self.notify("Selecione um modelo compatível com geração de texto.", severity="warning")
            return
        if model.id not in self.preferences.favorites:
            self.preferences.favorites.append(model.id)
            if self.preferences.default_model is None:
                self.preferences.default_model = model.id
        self.refresh_tables()

    async def check_models(self, models: list[str]) -> None:
        self.query_one("#test-one", Button).disabled = True
        self.query_one("#test-all", Button).disabled = True
        self.query_one("#stop-tests", Button).disabled = False
        # Sequential requests avoid bursts of rate-limit errors. Stop on 429.
        try:
            for index, model_id in enumerate(models, 1):
                self.testing.add(model_id)
                self.query_one("#check-progress", Static).update(
                    f"Testando {index}/{len(models)}: {model_id}"
                )
                self.refresh_tables()
                result = await self.service.check(model_id)
                self.preferences.checks[model_id] = result
                self.testing.discard(model_id)
                self.refresh_tables()
                if result.http_code == 429:
                    self.notify("Testes interrompidos: limite/cota do Gemini.", severity="warning")
                    break
            self.query_one("#check-progress", Static).update(
                "Testes finalizados. Clique Salvar para manter os resultados."
            )
        finally:
            self.testing.clear()
            self.query_one("#test-one", Button).disabled = False
            self.query_one("#test-all", Button).disabled = False
            self.query_one("#stop-tests", Button).disabled = True
            self.refresh_tables()

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "add-favorite":
            self.add_favorite()
        elif action == "remove-favorite":
            if self.selected_model in self.preferences.favorites:
                self.preferences.favorites.remove(self.selected_model)
                if self.preferences.default_model == self.selected_model:
                    self.preferences.default_model = None
                self.refresh_tables()
        elif action == "set-default":
            model = self.models.get(self.selected_model or "")
            if model and model.compatible and model.id in self.preferences.favorites:
                self.preferences.default_model = model.id
                self.refresh_tables()
            else:
                self.notify(
                    "Selecione um favorito compatível presente no catálogo.", severity="warning"
                )
        elif action == "refresh-catalog":
            self.run_worker(self.load_catalog(), group="catalog", exclusive=True)
        elif action in ("test-one", "test-all"):
            models = [
                model.id
                for model in self.models.values()
                if model.compatible and (action == "test-all" or model.id == self.selected_model)
            ]
            if models:
                self.testing_worker = self.run_worker(
                    self.check_models(models), group="checks", exclusive=True
                )
            else:
                self.notify("Nenhum modelo compatível selecionado.", severity="warning")
        elif action == "stop-tests":
            if self.testing_worker:
                self.testing_worker.cancel()
            self.query_one("#check-progress", Static).update("Testes cancelados.")
        elif action == "save-models":
            model = self.models.get(self.preferences.default_model or "")
            if not model or not model.compatible:
                self.notify("Defina um favorito compatível como padrão.", severity="warning")
                return
            if self.testing:
                self.notify("Conclua ou pare os testes antes de salvar.", severity="warning")
                return
            try:
                self.preferences.configured = True
                self.store.save(self.preferences)
            except (OSError, ValueError):
                self.notify("Não foi possível salvar as preferências.", severity="error")
                return
            self.dismiss(True)
        elif action == "cancel-models":
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(False)


class ModelSelectionModal(ModalScreen[tuple[str, str] | None]):
    DEFAULT_CSS = """
    ModelSelectionModal { align: center middle; background: $background 50%; }
    #model-selection { width: 76; height: auto; padding: 1 2; border: round $primary; }
    #selection-status { height: auto; max-height: 4; }
    #manage-models { width: 100%; margin-top: 1; }
    ModelSelectionModal .actions { height: 5; padding-top: 1; align: right middle; }
    ModelSelectionModal .actions Button { min-width: 14; margin-left: 1; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancelar")]

    def __init__(
        self,
        default_provider: str = "gemini",
        *,
        store: PreferenceStore | None = None,
        service: GeminiService | None = None,
    ) -> None:
        super().__init__()
        self.store = store or PreferenceStore()
        self.service = service or GeminiService()
        self.models: dict[str, ModelInfo] = {}

    def compose(self) -> ComposeResult:
        with Container(id="model-selection"):
            yield Label("Provedor: Gemini")
            yield Label("Modelo escolhido")
            yield Select([], id="select-model", disabled=True)
            yield Static("Carregando modelos...", id="selection-status", markup=False)
            yield Button("Gerenciar modelos", id="manage-models")
            with Horizontal(classes="actions"):
                yield Button("Cancelar", id="btn-cancel")
                yield Button("Confirmar", id="btn-confirm", variant="success", disabled=True)

    def on_mount(self) -> None:
        self.run_worker(self.load_choices(), group="choices", exclusive=True)

    async def load_choices(self) -> None:
        selector = self.query_one("#select-model", Select)
        confirm = self.query_one("#btn-confirm", Button)
        status = self.query_one("#selection-status", Static)
        selector.disabled = confirm.disabled = True
        selector.set_options([])
        try:
            prefs = self.store.load()
            catalog = await self.service.list_models()
            self.models = {model.id: model for model in catalog if model.compatible}
            choices = prefs.favorites if prefs.configured else list(self.models)
            options = [
                (
                    model_id + (" (ausente/incompatível)" if model_id not in self.models else ""),
                    model_id,
                )
                for model_id in choices
            ]
            selector.set_options(options)
            selector.disabled = not options
            default = (
                prefs.default_model
                if prefs.configured
                else os.environ.get("GEMINI_DEFAULT_MODEL", "")
            )
            if default in choices and default in self.models:
                selector.value = default
            elif not prefs.configured and choices:
                selector.value = choices[0]
            status.update(
                "Padrão ausente/incompatível: escolha outro modelo ou gerencie seus favoritos."
                if prefs.configured and default not in self.models
                else "Escolha um favorito. Os testes de disponibilidade ficam em Gerenciar modelos."
                if prefs.configured
                else "Configure seus favoritos em Gerenciar modelos."
            )
            self.update_confirm()
        except Exception:
            status.update(
                "Não foi possível carregar os modelos. Verifique chave, conexão e preferências."
            )

    @on(Select.Changed, "#select-model")
    def update_confirm(self) -> None:
        if self.is_mounted:
            value = self.query_one("#select-model", Select).value
            self.query_one("#btn-confirm", Button).disabled = value not in self.models

    @on(Button.Pressed, "#manage-models")
    def manage_models(self) -> None:
        try:
            manager = ModelManagerScreen(self.store, self.service)
        except (ValueError, OSError):
            self.notify("Preferências inválidas; arquivo preservado.", severity="error")
            return
        self.app.push_screen(manager, self.manager_closed)

    def manager_closed(self, saved: bool) -> None:
        if saved:
            self.run_worker(self.load_choices(), group="choices", exclusive=True)

    @on(Button.Pressed, "#btn-confirm")
    def on_confirm(self) -> None:
        value = self.query_one("#select-model", Select).value
        if value in self.models:
            self.dismiss(("gemini", str(value)))

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
