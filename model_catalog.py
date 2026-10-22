"""Gemini catalog, generation checks and local model preferences."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
PREFERENCES_PATH = Path(__file__).resolve().parent / "model_preferences.json"


class InvalidGenerationResponse(ValueError):
    """An HTTP 200 response did not contain usable generated text."""


@dataclass
class ModelInfo:
    id: str
    version: str = "Não informada"
    family: str = "Outros"
    compatible: bool = False
    description: str = ""

    @classmethod
    def from_api(cls, data: dict) -> ModelInfo:
        model_id = data["name"].removeprefix("models/")
        match = re.search(r"gemini-(\d+(?:\.\d+)?)", model_id)
        # generateContent also covers specialized audio/image endpoints. They
        # cannot use the text-only request used by this application.
        specialized = any(part in model_id for part in ("tts", "image", "audio", "robotics"))
        return cls(
            id=model_id,
            version=match[1] if match else str(data.get("version") or "Não informada"),
            family="Gemini" if model_id.startswith("gemini-") else model_id.split("-")[0],
            compatible="generateContent" in data.get("supportedGenerationMethods", [])
            and not specialized,
            description=data.get("description", ""),
        )


@dataclass
class CheckResult:
    status: str
    checked_at: str
    duration_ms: int
    http_code: int | None = None
    detail: str = ""


@dataclass
class ModelPreferences:
    configured: bool = False
    favorites: list[str] = field(default_factory=list)
    default_model: str | None = None
    catalog: list[ModelInfo] = field(default_factory=list)
    checks: dict[str, CheckResult] = field(default_factory=dict)


class PreferenceStore:
    def __init__(self, path: Path = PREFERENCES_PATH) -> None:
        self.path = path

    def load(self) -> ModelPreferences:
        if not self.path.exists():
            return ModelPreferences()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("gemini"), dict):
                raise ValueError("Estrutura de preferências inválida.")
            if data.get("schema_version") != 1:
                raise ValueError("Versão de preferências não suportada.")
            prefs = data["gemini"]
            favorites = prefs["favorites"]
            default = prefs["default_model"]
            if (
                not isinstance(favorites, list)
                or not all(isinstance(item, str) for item in favorites)
                or (default is not None and default not in favorites)
                or not isinstance(prefs["configured"], bool)
            ):
                raise ValueError("Favoritos ou padrão inválidos.")
            return ModelPreferences(
                configured=prefs["configured"],
                favorites=list(dict.fromkeys(favorites)),
                default_model=default,
                catalog=[ModelInfo(**item) for item in prefs.get("catalog", [])],
                checks={
                    key: CheckResult(**value) for key, value in prefs.get("checks", {}).items()
                },
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Preferências de modelos inválidas; arquivo preservado.") from exc

    def save(self, preferences: ModelPreferences) -> None:
        if preferences.default_model not in preferences.favorites:
            raise ValueError("Escolha um modelo favorito como padrão.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "gemini": asdict(preferences)}
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)


class GeminiService:
    """Use the same text generation path for health checks and meeting summaries."""

    def __init__(
        self, api_key: str | None = None, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")
        self.transport = transport

    def _client(self, timeout: float = 120) -> httpx.AsyncClient:
        if not self.api_key:
            raise ValueError("Configure GEMINI_API_KEY no arquivo .env.")
        return httpx.AsyncClient(
            base_url=GEMINI_BASE + "/",
            headers={"x-goog-api-key": self.api_key},
            timeout=timeout,
            transport=self.transport,
            trust_env=self.transport is None,
        )

    async def list_models(self) -> list[ModelInfo]:
        models: dict[str, ModelInfo] = {}
        params = {"pageSize": "1000"}
        async with self._client(20) as client:
            while True:
                response = await client.get("models", params=params)
                response.raise_for_status()
                data = response.json()
                for item in data.get("models", []):
                    model = ModelInfo.from_api(item)
                    models[model.id] = model
                token = data.get("nextPageToken")
                if not token:
                    break
                params["pageToken"] = token
        return sorted(models.values(), key=lambda item: item.id)

    async def generate(self, model: str, text: str, *, timeout: float = 120) -> str:
        async with self._client(timeout) as client:
            response = await client.post(
                f"models/{model}:generateContent",
                json={"contents": [{"parts": [{"text": text}]}]},
            )
            response.raise_for_status()
            candidates = response.json().get("candidates") or [{}]
            parts = candidates[0].get("content", {}).get("parts", [])
            result = "".join(
                part.get("text", "") for part in parts if not part.get("thought", False)
            ).strip()
            if not result:
                raise InvalidGenerationResponse(
                    "Resposta sem texto utilizável (bloqueada ou incompatível)."
                )
            return result

    async def check(self, model: str) -> CheckResult:
        started = time.monotonic()
        status, code, detail = "Disponível", 200, "Geração de texto concluída."
        try:
            await self.generate(model, "Responda apenas com a palavra OK.", timeout=30)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            status = {
                400: "Requisição rejeitada",
                401: "Autenticação/permissão",
                403: "Autenticação/permissão",
                404: "Não encontrado",
                429: "Limite/cota",
            }.get(code, "Falha do serviço" if code >= 500 else "Erro HTTP")
            # Do not persist provider messages: they may echo credentials or input.
            detail = f"HTTP {code}. Verifique acesso, limites e compatibilidade do modelo."
        except httpx.TimeoutException:
            status, code, detail = "Tempo esgotado", None, "O teste excedeu 30 segundos."
        except httpx.RequestError:
            status, code, detail = "Sem conexão", None, "Não foi possível acessar o Gemini."
        except InvalidGenerationResponse:
            status, code, detail = (
                "Resposta inválida/incompatível",
                200,
                ("HTTP 200, mas a geração não retornou texto utilizável."),
            )
        except (ValueError, KeyError, IndexError, TypeError):
            status, code, detail = (
                "Resposta inválida/configuração",
                None,
                ("Verifique a chave de API e a compatibilidade da resposta textual."),
            )
        return CheckResult(
            status=status,
            checked_at=datetime.now(UTC).isoformat(),
            duration_ms=round((time.monotonic() - started) * 1000),
            http_code=code,
            detail=detail,
        )
