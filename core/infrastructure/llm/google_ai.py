from collections.abc import Iterator
import json
from pathlib import Path
import threading
from typing import Any, ClassVar

import requests

from domain.settings.exceptions import InvalidServiceCredentialsError
from domain.settings.models import ModelParameters, ServiceSettings
from domain.settings.services import SettingsService
from infrastructure.google_ai_common import (
    build_google_generate_payload,
    build_google_headers,
    check_google_candidate_finish_reason,
    check_google_response_blocks,
    encode_image_inline_part,
    ensure_google_response_ok,
    extract_text_from_google_response,
    normalize_google_model_id,
)
from infrastructure.http_utils import decode_utf8_line
from infrastructure.llm.base import BaseLLMProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class GoogleAILLMProvider(BaseLLMProvider):
    PROVIDER_ID: ClassVar[str] = "google_ai"
    DISPLAY_NAME: ClassVar[str] = "Google AI Cloud (Gemini API)"
    BADGE_LABEL: ClassVar[str] = "Cloud"
    IS_CLOUD: ClassVar[bool] = True
    DESCRIPTION: ClassVar[str] = (
        "Sofort startklar ohne eigene GPU über einen API-Key aus Google AI Studio. "
        "Unterstützt Text, Vision und optional Bildgenerierung."
    )
    DEFAULT_BASE_URL: ClassVar[str] = Config.GOOGLE_AI_BASE_URL
    DEFAULT_API_KEY: ClassVar[str] = Config.DEFAULT_GOOGLE_AI_API_KEY

    RECOMMENDED_ROLEPLAY_MODEL: ClassVar[str] = "gemini-4-hydrogen"
    RECOMMENDED_MEMORY_MODEL: ClassVar[str] = "gemini-4-hydrogen"
    RECOMMENDED_ASSISTANT_MODEL: ClassVar[str] = "gemini-4-hydrogen"
    RECOMMENDED_VISION_MODEL: ClassVar[str] = "gemini-4-hydrogen"
    RECOMMENDED_CLASSIFICATION_MODEL: ClassVar[str] = "gemini-3.1-flash-lite"

    DEFAULT_MODEL_ROLES: ClassVar[dict[str, dict[str, str]]] = {
        "roleplay": {
            "role_name": "Roleplay",
            "model": RECOMMENDED_ROLEPLAY_MODEL,
            "description": "Schnelles Cloud-Sprachmodell für narrative Dialoge und Rollenspiel.",
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
            "description": "Multimodale Analyse von Porträts, Schauplatz-Hintergründen und Chat-Bildern.",
        },
        "classification": {
            "role_name": "Classification",
            "model": RECOMMENDED_CLASSIFICATION_MODEL,
            "description": "Ultraschnelle und kosteneffiziente Erkennung von Emotionen und Ortswechseln.",
        },
    }

    _MODEL_CTX_CACHE: dict[str, int] = {}
    _THINKING_FALLBACK_CACHE: dict[str, str] = {}
    _CATALOG_CACHE: dict[tuple[str, int], tuple[float, tuple[list[str], list[str]]]] = {}
    _CATALOG_TTL_SECONDS: ClassVar[float] = 60.0
    _CACHE_LOCK: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def supports_model_management(cls) -> bool:
        return False

    @classmethod
    def is_model_compatible(cls, model_name: str) -> bool:
        cleaned = (model_name or "").strip().lower()
        if not cleaned:
            return False
        return ":" not in cleaned and not cleaned.startswith("llama")

    @classmethod
    def get_default_config(cls) -> dict[str, str]:
        return {"api_key": cls.DEFAULT_API_KEY}

    @classmethod
    def validate_active_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
        clear_secret: bool = False,
    ) -> dict[str, str]:
        if clear_secret:
            raise InvalidServiceCredentialsError(
                "Google AI API-Key darf nicht gelöscht werden, solange Google AI aktiv ist."
            )
        raw_key = (
            (submitted.get("api_key") or "").strip()
            or (existing.get("api_key") or "").strip()
            or cls.DEFAULT_API_KEY.strip()
        )
        validated = SettingsService.validate_secret("google_ai_api_key", raw_key)
        return {"api_key": validated}

    @classmethod
    def validate_inactive_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
        clear_secret: bool = False,
    ) -> dict[str, str]:
        if clear_secret:
            return {"api_key": ""}
        raw_key = (submitted.get("api_key") or "").strip()
        if raw_key:
            return {"api_key": SettingsService.validate_secret("google_ai_api_key", raw_key)}
        return {"api_key": (existing.get("api_key") or "").strip()}

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "GoogleAILLMProvider":
        cfg = settings.get_llm_config(cls.PROVIDER_ID)
        api_key = cfg.get("api_key") or cls.DEFAULT_API_KEY
        return cls(api_key=api_key, base_url=cls.DEFAULT_BASE_URL)

    def format_stream_error(self, exc: Exception, model: str) -> str:
        raw_err = str(exc)
        lower_err = raw_err.lower()
        if "401" in lower_err or "403" in lower_err or "api key" in lower_err or "api_key" in lower_err:
            return (
                "Google AI API-Key ungültig oder Berechtigung fehlt. "
                "Bitte im Admin-Panel unter 'Services & Modelle' prüfen."
            )
        if "404" in lower_err or "not found" in lower_err:
            return (
                f"Google AI Modell '{model}' wurde nicht gefunden oder wird nicht unterstützt."
            )
        if "429" in lower_err or "quota" in lower_err or "rate" in lower_err:
            return (
                "Google AI Rate-Limit oder Kontingent erschöpft. Bitte kurz warten und erneut versuchen."
            )
        if "blocked" in lower_err or "safety" in lower_err:
            return "Google AI hat die Antwort aufgrund von Sicherheitsrichtlinien blockiert."
        return f"Google AI Verbindungsfehler ({model}): {raw_err}"

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: tuple[float, float] = (10.0, 120.0),
    ) -> None:
        self.api_key: str = (api_key or "").strip()
        self.base_url: str = base_url.strip().rstrip("/")
        self.request_timeout: tuple[float, float] = request_timeout
        self._session: requests.Session = requests.Session()

    def generate_stream(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        think: bool | None = None,
    ) -> Iterator[str]:
        clean_model = normalize_google_model_id(model)
        if not clean_model:
            raise InfrastructureError("Google AI model name must not be empty.")

        headers = build_google_headers(self.api_key)
        payload = self._build_payload(
            parts=[{"text": prompt}],
            params=params,
            stop=stop,
            format=None,
            think=think,
        )
        url = f"{self.base_url}/models/{clean_model}:streamGenerateContent?alt=sse"
        try:
            response = self._post_with_thinking_fallback(
                url=url, headers=headers, payload=payload, stream=True
            )
            with response:
                response.encoding = "utf-8"
                ensure_google_response_ok(response, "Google AI streaming generation")
                emitted_any = False
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line = decode_utf8_line(raw_line)
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError as exc:
                        raise InfrastructureError(
                            f"Invalid JSON chunk received from Google AI stream: {data_str}"
                        ) from exc

                    self._check_response_blocks(chunk)
                    text_piece = self._extract_text_from_response(chunk)
                    if text_piece:
                        emitted_any = True
                        yield text_piece
                    self._check_candidate_finish_reason(chunk, emitted_any=emitted_any)
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to stream response from Google AI API: {exc}"
            ) from exc

    def _execute_content_request(
        self,
        *,
        model: str,
        parts: list[dict[str, Any]],
        params: ModelParameters,
        stop: list[str] | None = None,
        format: str | dict | None = None,
        think: bool | None = None,
        context_label: str = "Google AI generation",
        error_prefix: str = "Failed to generate response from Google AI API",
    ) -> str:
        clean_model = normalize_google_model_id(model)
        if not clean_model:
            raise InfrastructureError("Google AI model name must not be empty.")

        headers = build_google_headers(self.api_key)
        payload = self._build_payload(
            parts=parts,
            params=params,
            stop=stop,
            format=format,
            think=think,
        )
        url = f"{self.base_url}/models/{clean_model}:generateContent"
        try:
            response = self._post_with_thinking_fallback(
                url=url, headers=headers, payload=payload, stream=False
            )
            ensure_google_response_ok(response, context_label)
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(f"{error_prefix}: {exc}") from exc

        self._check_response_blocks(data)
        text = self._extract_text_from_response(data).strip()
        if not text:
            self._check_candidate_finish_reason(data, emitted_any=False)
        return text

    def generate(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        format: str | dict | None = None,
        think: bool | None = None,
    ) -> str:
        return self._execute_content_request(
            model=model,
            parts=[{"text": prompt}],
            params=params,
            stop=stop,
            format=format,
            think=think,
            context_label="Google AI generation",
            error_prefix="Failed to generate response from Google AI API",
        )

    def analyze_image(self, image_path: Path, prompt: str, model: str) -> str:
        image_part = encode_image_inline_part(image_path)
        return self._execute_content_request(
            model=model,
            parts=[{"text": prompt}, image_part],
            params=ModelParameters(num_ctx=4096, temperature=0.3, top_p=0.9, repeat_penalty=1.0),
            stop=None,
            format=None,
            think=False,
            context_label="Google AI vision analysis",
            error_prefix="Failed to analyze image via Google AI API",
        )

    def list_model_catalog(self) -> tuple[list[str], list[str]]:
        import time

        cache_key = (self.base_url, hash(self.api_key))
        now = time.monotonic()
        with self._CACHE_LOCK:
            cached = self._CATALOG_CACHE.get(cache_key)
            if cached and (now - cached[0]) < self._CATALOG_TTL_SECONDS:
                return list(cached[1][0]), list(cached[1][1])

        headers = build_google_headers(self.api_key)
        text_models: list[str] = []
        image_models: list[str] = []
        page_token: str | None = None

        try:
            while True:
                params: dict[str, Any] = {"pageSize": 100}
                if page_token:
                    params["pageToken"] = page_token
                response = self._session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    params=params,
                    timeout=self.request_timeout,
                )
                response.encoding = "utf-8"
                ensure_google_response_ok(response, "Google AI list models")
                data = response.json()

                for entry in data.get("models", []):
                    if not isinstance(entry, dict):
                        continue
                    methods = entry.get("supportedGenerationMethods") or []
                    if "generateContent" not in methods:
                        continue
                    raw_name = str(entry.get("name") or "")
                    short_name = normalize_google_model_id(raw_name)
                    if not short_name:
                        continue

                    input_limit = entry.get("inputTokenLimit")
                    if isinstance(input_limit, int) and input_limit > 0:
                        with self._CACHE_LOCK:
                            self._MODEL_CTX_CACHE[f"{self.base_url}::{short_name}"] = input_limit

                    lower_name = short_name.lower()
                    if "image" in lower_name or "imagen" in lower_name:
                        image_models.append(short_name)
                    elif (
                        "embedding" not in lower_name
                        and "native-audio" not in lower_name
                        and "-tts" not in lower_name
                        and "lyria" not in lower_name
                    ):
                        text_models.append(short_name)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to list models from Google AI API: {exc}"
            ) from exc

        with self._CACHE_LOCK:
            self._CATALOG_CACHE[cache_key] = (now, (list(text_models), list(image_models)))
        return text_models, image_models

    def list_models(self) -> list[str]:
        text_models, _ = self.list_model_catalog()
        return text_models

    def list_image_models(self) -> list[str]:
        _, image_models = self.list_model_catalog()
        return image_models

    def pull_model(self, name: str) -> Iterator[dict]:
        raise InfrastructureError(
            "Model pull is only supported when Ollama is the active backend."
        )

    def delete_model(self, name: str) -> bool:
        raise InfrastructureError(
            "Model deletion is only supported when Ollama is the active backend."
        )

    def check_health(self) -> bool:
        if not self.api_key:
            return False
        try:
            response = self._session.get(
                f"{self.base_url}/models",
                headers=build_google_headers(self.api_key),
                params={"pageSize": 1},
                timeout=(5.0, 5.0),
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_model_context_length(self, model: str) -> int | None:
        clean_model = normalize_google_model_id(model)
        if not clean_model or not self.api_key:
            return None
        cache_key = f"{self.base_url}::{clean_model}"
        with self._CACHE_LOCK:
            if cache_key in self._MODEL_CTX_CACHE:
                return self._MODEL_CTX_CACHE[cache_key]

        try:
            response = self._session.get(
                f"{self.base_url}/models/{clean_model}",
                headers=build_google_headers(self.api_key),
                timeout=(3.0, 5.0),
            )
            response.encoding = "utf-8"
            if response.status_code != 200:
                return None
            data = response.json()
            limit = data.get("inputTokenLimit")
            if isinstance(limit, int) and limit > 0:
                self._MODEL_CTX_CACHE[cache_key] = limit
                return limit
        except (requests.RequestException, ValueError):
            return None
        return None

    def _post_with_thinking_fallback(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        stream: bool,
    ) -> requests.Response:
        effective_payload = payload
        cached_mode = self._THINKING_FALLBACK_CACHE.get(url)
        gen_cfg_orig = payload.get("generationConfig") or {}
        if cached_mode and "thinkingConfig" in gen_cfg_orig:
            effective_payload = dict(payload)
            gen_cfg = dict(gen_cfg_orig)
            if cached_mode == "none":
                gen_cfg.pop("thinkingConfig", None)
            elif cached_mode == "low" and gen_cfg.get("thinkingConfig", {}).get("thinkingLevel") == "minimal":
                gen_cfg["thinkingConfig"] = {
                    **gen_cfg["thinkingConfig"],
                    "thinkingLevel": "low",
                }
            effective_payload["generationConfig"] = gen_cfg

        response = self._session.post(
            url,
            headers=headers,
            json=effective_payload,
            stream=stream,
            timeout=self.request_timeout,
        )
        response.encoding = "utf-8"

        thinking_cfg = (effective_payload.get("generationConfig") or {}).get("thinkingConfig")
        if (
            response.status_code == 400
            and isinstance(thinking_cfg, dict)
            and "thinking" in (response.text or "").lower()
        ):
            if thinking_cfg.get("thinkingLevel") == "minimal":
                response.close()
                low_payload = dict(effective_payload)
                low_gen_cfg = dict(effective_payload["generationConfig"])
                low_gen_cfg["thinkingConfig"] = {
                    **thinking_cfg,
                    "thinkingLevel": "low",
                }
                low_payload["generationConfig"] = low_gen_cfg
                response = self._session.post(
                    url,
                    headers=headers,
                    json=low_payload,
                    stream=stream,
                    timeout=self.request_timeout,
                )
                response.encoding = "utf-8"
                if response.status_code < 400:
                    self._THINKING_FALLBACK_CACHE[url] = "low"
                    return response

            if response.status_code == 400 and "thinking" in (response.text or "").lower():
                response.close()
                self._THINKING_FALLBACK_CACHE[url] = "none"
                fallback_payload = dict(effective_payload)
                gen_cfg = dict(effective_payload["generationConfig"])
                gen_cfg.pop("thinkingConfig", None)
                fallback_payload["generationConfig"] = gen_cfg
                response = self._session.post(
                    url,
                    headers=headers,
                    json=fallback_payload,
                    stream=stream,
                    timeout=self.request_timeout,
                )
                response.encoding = "utf-8"
        return response

    @staticmethod
    def _build_payload(
        parts: list[dict[str, Any]],
        params: ModelParameters,
        stop: list[str] | None,
        format: str | dict | None,
        think: bool | None,
    ) -> dict[str, Any]:
        return build_google_generate_payload(
            parts=parts,
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_tokens,
            stop=stop,
            format=format,
            think=think,
        )

    @staticmethod
    def _extract_text_from_response(payload: dict[str, Any]) -> str:
        return extract_text_from_google_response(payload)

    @staticmethod
    def _check_response_blocks(payload: dict[str, Any]) -> None:
        check_google_response_blocks(payload)

    @staticmethod
    def _check_candidate_finish_reason(
        payload: dict[str, Any],
        emitted_any: bool,
    ) -> None:
        check_google_candidate_finish_reason(payload, emitted_any)
