from collections.abc import Iterator
import json
from pathlib import Path
import re
import threading
from typing import Any, ClassVar

import requests

from domain.settings.models import ModelParameters, ServiceSettings
from infrastructure.http_utils import (
    UrlBackendConfigMixin,
    decode_utf8_line,
    encode_image_base64,
    ensure_response_ok,
)
from infrastructure.llm.base import BaseLLMProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class OllamaLLMProvider(UrlBackendConfigMixin, BaseLLMProvider):
    PROVIDER_ID: ClassVar[str] = "ollama"
    DISPLAY_NAME: ClassVar[str] = "Ollama (Lokal / Self-Hosted)"
    BADGE_LABEL: ClassVar[str] = "Lokal"
    DESCRIPTION: ClassVar[str] = (
        "Volle Datenkontrolle auf eigener Hardware oder einem eigenen Ollama-Server. "
        "Modelle werden lokal geladen und verwaltet."
    )
    DEFAULT_BASE_URL: ClassVar[str] = Config.DEFAULT_OLLAMA_URL
    URL_FIELD_NAME: ClassVar[str] = "ollama_url"

    RECOMMENDED_ROLEPLAY_MODEL: ClassVar[str] = (
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
    )
    RECOMMENDED_MEMORY_MODEL: ClassVar[str] = (
        "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
    )
    RECOMMENDED_ASSISTANT_MODEL: ClassVar[str] = "gemma4:e4b"
    RECOMMENDED_VISION_MODEL: ClassVar[str] = "gemma4:e4b"
    RECOMMENDED_CLASSIFICATION_MODEL: ClassVar[str] = "llama3.2:1b"

    DEFAULT_MODEL_ROLES: ClassVar[dict[str, dict[str, str]]] = {
        "roleplay": {
            "role_name": "Roleplay",
            "model": RECOMMENDED_ROLEPLAY_MODEL,
            "description": "Narrative Dialog-Generierung und Rollenspiel im Chat.",
        },
        "memory": {
            "role_name": "Memory",
            "model": RECOMMENDED_MEMORY_MODEL,
            "description": "Erstellt alle 10 Nachrichten episodische Zusammenfassungen und aktualisiert den Chat-Titel.",
        },
        "assistant": {
            "role_name": "Assistant",
            "model": RECOMMENDED_ASSISTANT_MODEL,
            "description": "Zuständig für Sparkle-Optimierung (✨), Übersetzungen und Bild-Prompts.",
        },
        "vision": {
            "role_name": "Vision",
            "model": RECOMMENDED_VISION_MODEL,
            "description": "Optische Analyse von Porträts, Schauplatz-Hintergründen und Chat-Bildern.",
        },
        "classification": {
            "role_name": "Classification",
            "model": RECOMMENDED_CLASSIFICATION_MODEL,
            "description": "Schnelle Erkennung von Emotionen (Avatar-Sprites) und Ortswechsel-Vorschlägen.",
        },
    }

    @classmethod
    def supports_model_management(cls) -> bool:
        return True

    @classmethod
    def is_model_compatible(cls, model_name: str) -> bool:
        cleaned = (model_name or "").strip().lower()
        if not cleaned:
            return False
        return not cleaned.startswith("gemini-") and not cleaned.startswith("models/gemini-")

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "OllamaLLMProvider":
        cfg = settings.get_llm_config(cls.PROVIDER_ID)
        base_url = cfg.get("base_url") or cls.DEFAULT_BASE_URL
        return cls(base_url=base_url)

    def format_stream_error(self, exc: Exception, model: str) -> str:
        raw_err = str(exc)
        if (
            "Failed to stream response from Ollama" in raw_err
            or "Connection refused" in raw_err
            or "Failed to establish a new connection" in raw_err
            or "Max retries exceeded" in raw_err
        ):
            return (
                f"Verbindung zu Ollama ({model}) fehlgeschlagen oder unterbrochen. "
                "Bitte stelle sicher, dass der Ollama-Dienst läuft."
            )
        if "not found" in raw_err.lower():
            return (
                f"Ollama-Modell '{model}' wurde nicht gefunden. "
                f"Bitte in Ollama laden (ollama run {model})."
            )
        return f"Ollama-Verbindungsfehler ({model}): {raw_err}"

    _SCHEMA_UNSUPPORTED_CACHE: set[str] = set()
    _CACHE_LOCK: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: tuple[float, float] = (10.0, 120.0),
        pull_timeout: tuple[float, float] = (10.0, 600.0),
    ) -> None:
        self.base_url: str = base_url.strip().rstrip("/")
        self.request_timeout: tuple[float, float] = request_timeout
        self.pull_timeout: tuple[float, float] = pull_timeout
        self._session: requests.Session = requests.Session()

    def generate_stream(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        think: bool | None = None,
    ) -> Iterator[str]:
        options = self._build_options(params)
        if stop:
            options["stop"] = stop
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "10m",
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        try:
            response = self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.request_timeout,
            )
            response.encoding = "utf-8"
            if response.status_code == 400 and think is not None and "think" in response.text.lower():
                response.close()
                payload.pop("think", None)
                response = self._session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    stream=True,
                    timeout=self.request_timeout,
                )
                response.encoding = "utf-8"
            with response:
                response.encoding = "utf-8"
                ensure_response_ok(response, "Ollama streaming generation")
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line_str = decode_utf8_line(raw_line)
                    try:
                        chunk = json.loads(line_str)
                    except json.JSONDecodeError as exc:
                        raise InfrastructureError(
                            f"Invalid JSON chunk received from Ollama stream: {line_str}"
                        ) from exc
                    if "error" in chunk:
                        raise InfrastructureError(
                            f"Ollama generation error: {chunk['error']}"
                        )
                    token = chunk.get("response", "")
                    if token:
                        yield str(token)
                    if chunk.get("done") is True:
                        break
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to stream response from Ollama at '{self.base_url}': {exc}"
            ) from exc

    def generate(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        format: str | dict | None = None,
        think: bool | None = None,
    ) -> str:
        options = self._build_options(params)
        if stop:
            options["stop"] = stop
        schema_cache_key = f"{self.base_url}::{model}"
        effective_format: str | dict | None = (
            "json"
            if isinstance(format, dict) and schema_cache_key in self._SCHEMA_UNSUPPORTED_CACHE
            else format
        )
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": options,
        }
        if effective_format:
            payload["format"] = effective_format
        if think is not None:
            payload["think"] = think
        try:
            response = self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.request_timeout,
            )
            if response.status_code == 400 and think is not None and "think" in response.text.lower():
                payload.pop("think", None)
                response = self._session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.request_timeout,
                )
            if (
                response.status_code == 400
                and isinstance(effective_format, dict)
                and "format" in response.text.lower()
            ):
                self._SCHEMA_UNSUPPORTED_CACHE.add(schema_cache_key)
                payload["format"] = "json"
                response = self._session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.request_timeout,
                )
            self._ensure_ok(response, "Ollama generation")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to generate response from Ollama at '{self.base_url}': {exc}"
            ) from exc

        if "error" in data:
            raise InfrastructureError(f"Ollama generation error: {data['error']}")
        return str(data.get("response", "")).strip()

    def analyze_image(self, image_path: Path, prompt: str, model: str) -> str:
        encoded_image = encode_image_base64(image_path)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False,
        }
        try:
            response = self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.request_timeout,
            )
            ensure_response_ok(response, "Ollama vision analysis")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to analyze image via Ollama at '{self.base_url}': {exc}"
            ) from exc

        if "error" in data:
            raise InfrastructureError(f"Ollama vision analysis error: {data['error']}")
        return str(data.get("response", "")).strip()

    def list_models(self) -> list[str]:
        try:
            response = self._session.get(
                f"{self.base_url}/api/tags",
                timeout=self.request_timeout,
            )
            ensure_response_ok(response, "Ollama list models")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to list models from Ollama at '{self.base_url}': {exc}"
            ) from exc

        models_raw = data.get("models", [])
        if not isinstance(models_raw, list):
            return []
        return [
            str(entry["name"])
            for entry in models_raw
            if isinstance(entry, dict) and entry.get("name")
        ]

    def pull_model(self, name: str) -> Iterator[dict]:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise InfrastructureError("Model name for pull_model must not be empty.")

        payload = {"name": cleaned_name, "stream": True}
        try:
            with self._session.post(
                f"{self.base_url}/api/pull",
                json=payload,
                stream=True,
                timeout=self.pull_timeout,
            ) as response:
                response.encoding = "utf-8"
                ensure_response_ok(response, f"Ollama pull model '{cleaned_name}'")
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line_str = decode_utf8_line(raw_line)
                    try:
                        event = json.loads(line_str)
                    except json.JSONDecodeError as exc:
                        raise InfrastructureError(
                            f"Invalid JSON status received during model pull: {line_str}"
                        ) from exc
                    if "error" in event:
                        raise InfrastructureError(
                            f"Ollama model pull error for '{cleaned_name}': {event['error']}"
                        )
                    if isinstance(event, dict):
                        yield event
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to pull model '{cleaned_name}' from Ollama at '{self.base_url}': {exc}"
            ) from exc

    def delete_model(self, name: str) -> bool:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise InfrastructureError("Model name for delete_model must not be empty.")

        try:
            response = self._session.delete(
                f"{self.base_url}/api/delete",
                json={"name": cleaned_name},
                timeout=self.request_timeout,
            )
            if response.status_code == 404:
                return False
            ensure_response_ok(response, f"Ollama delete model '{cleaned_name}'")
            return True
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to delete model '{cleaned_name}' from Ollama at '{self.base_url}': {exc}"
            ) from exc

    def check_health(self) -> bool:
        try:
            response = self._session.get(
                f"{self.base_url}/api/tags",
                timeout=(5.0, 5.0),
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    _MODEL_CTX_CACHE: dict[str, int] = {}

    def get_model_context_length(self, model: str) -> int | None:
        cleaned_name = model.strip() if isinstance(model, str) else ""
        if not cleaned_name:
            return None
        cache_key = f"{self.base_url}::{cleaned_name}"
        with self._CACHE_LOCK:
            if cache_key in self._MODEL_CTX_CACHE:
                return self._MODEL_CTX_CACHE[cache_key]

        try:
            response = self._session.post(
                f"{self.base_url}/api/show",
                json={"name": cleaned_name},
                timeout=(3.0, 5.0),
            )
            if response.status_code != 200:
                return None
            data = response.json()
        except (requests.RequestException, ValueError):
            return None

        params_str = str(data.get("parameters", "") or "")
        match = re.search(r"\bnum_ctx\s+(\d+)\b", params_str, re.IGNORECASE)
        if match:
            ctx_val = int(match.group(1))
            if ctx_val > 0:
                self._MODEL_CTX_CACHE[cache_key] = ctx_val
                return ctx_val

        model_info = data.get("model_info")
        if isinstance(model_info, dict):
            for key, val in model_info.items():
                if str(key).endswith(".context_length") and isinstance(val, int) and val > 0:
                    self._MODEL_CTX_CACHE[cache_key] = val
                    return val

        return None

    @staticmethod
    def _decode_utf8_line(raw_line: bytes | bytearray | str) -> str:
        if isinstance(raw_line, (bytes, bytearray)):
            return raw_line.decode("utf-8", errors="replace")
        return str(raw_line)

    @staticmethod
    def _build_options(params: ModelParameters) -> dict[str, int | float]:
        options: dict[str, int | float] = {
            "num_ctx": params.num_ctx,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "repeat_penalty": params.repeat_penalty,
        }
        if params.max_tokens is not None:
            options["num_predict"] = params.max_tokens
        return options
