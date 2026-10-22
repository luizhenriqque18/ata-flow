"""Model discovery and health checks never use a real API key or network."""

import json

import httpx
import pytest

from model_catalog import (
    CheckResult,
    GeminiService,
    ModelInfo,
    ModelPreferences,
    PreferenceStore,
)
from summarizer import GeminiSummarizer, SummarizerFactory


def test_preferences_roundtrip_and_no_secrets(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    prefs = ModelPreferences(
        configured=True,
        favorites=["gemini-test"],
        default_model="gemini-test",
        checks={"gemini-test": CheckResult("Disponível", "2026-10-22", 20, 200)},
    )
    store.save(prefs)
    assert store.load() == prefs
    assert json.loads(store.path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert "api_key" not in store.path.read_text(encoding="utf-8")


def test_invalid_preferences_are_preserved(tmp_path):
    store = PreferenceStore(tmp_path / "models.json")
    store.path.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError, match="preservado"):
        store.load()
    assert store.path.read_text() == "broken"


def test_atomic_save_failure_keeps_previous_preferences(tmp_path, monkeypatch):
    store = PreferenceStore(tmp_path / "models.json")
    prefs = ModelPreferences(favorites=["old"], default_model="old")
    store.save(prefs)
    monkeypatch.setattr("model_catalog.os.replace", lambda *args: (_ for _ in ()).throw(OSError()))
    with pytest.raises(OSError):
        store.save(ModelPreferences(favorites=["new"], default_model="new"))
    assert store.load() == prefs
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_catalog_pagination_and_metadata():
    pages = []

    def handler(request):
        assert request.headers["x-goog-api-key"] == "fake"
        assert "key=" not in str(request.url)
        pages.append(request.url.params.get("pageToken"))
        if len(pages) == 1:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-3.1-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ],
                    "nextPageToken": "page2",
                },
            )
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/embedding",
                        "supportedGenerationMethods": ["embedContent"],
                    }
                ]
            },
        )

    models = await GeminiService("fake", httpx.MockTransport(handler)).list_models()
    assert pages == [None, "page2"]
    assert len(models) == 2
    gemini = next(model for model in models if model.family == "Gemini")
    assert gemini.version == "3.1"
    assert gemini.compatible
    assert not next(model for model in models if model.id == "embedding").compatible


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,status",
    [
        (400, "Requisição rejeitada"),
        (401, "Autenticação/permissão"),
        (403, "Autenticação/permissão"),
        (404, "Não encontrado"),
        (429, "Limite/cota"),
        (500, "Falha do serviço"),
        (503, "Falha do serviço"),
    ],
)
async def test_health_classifies_http_errors(code, status):
    service = GeminiService(
        "fake",
        httpx.MockTransport(
            lambda request: httpx.Response(code, json={"error": {"message": "secret"}})
        ),
    )
    result = await service.check("gemini-test")
    assert result.status == status
    assert result.http_code == code
    assert "secret" not in result.detail
    assert result.checked_at


@pytest.mark.asyncio
async def test_health_requires_text_and_uses_generation_endpoint():
    def handler(request):
        assert request.url.path.endswith("/models/test:generateContent")
        assert "transcri" not in request.content.decode()
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})

    service = GeminiService("fake", httpx.MockTransport(handler))
    assert (await service.check("test")).status == "Disponível"
    service.transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    result = await service.check("test")
    assert result.status != "Disponível"
    assert result.http_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,status",
    [
        (httpx.ReadTimeout("timeout"), "Tempo esgotado"),
        (httpx.ConnectError("offline"), "Sem conexão"),
    ],
)
async def test_network_errors(exception, status):
    def handler(request):
        raise exception

    result = await GeminiService("fake", httpx.MockTransport(handler)).check("test")
    assert result.status == status
    assert result.http_code is None


@pytest.mark.asyncio
async def test_invalid_summary_is_an_exception():
    summarizer = GeminiSummarizer("test")
    summarizer.service = GeminiService(
        "fake", httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )
    with pytest.raises(ValueError, match="sem texto"):
        await summarizer.summarize("Discussão da reunião.")
    with pytest.raises(ValueError):
        SummarizerFactory.get_summarizer("ollama")


def test_specialized_models_are_not_text_defaults():
    assert not ModelInfo.from_api(
        {
            "name": "models/gemini-tts",
            "supportedGenerationMethods": ["generateContent"],
        }
    ).compatible
