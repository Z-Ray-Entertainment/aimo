import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import requests

from domain.settings.exceptions import InvalidServiceCredentialsError
from domain.settings.models import ModelParameters, ServiceSettings
from domain.settings.services import SettingsService
from infrastructure.google_ai_common import (
    DEFAULT_GOOGLE_AI_SAFETY_SETTINGS,
    build_google_headers,
    encode_image_inline_part,
    ensure_google_response_ok,
    normalize_google_model_id,
)
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
                    decoded_line = (
                        raw_line.decode("utf-8", errors="replace")
                        if isinstance(raw_line, (bytes, bytearray))
                        else str(raw_line)
                    )
                    line = decoded_line.strip()
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

    def generate(
        self,
        prompt: str,
        model: str,
        params: ModelParameters,
        stop: list[str] | None = None,
        format: str | dict | None = None,
        think: bool | None = None,
    ) -> str:
        clean_model = normalize_google_model_id(model)
        if not clean_model:
            raise InfrastructureError("Google AI model name must not be empty.")

        headers = build_google_headers(self.api_key)
        payload = self._build_payload(
            parts=[{"text": prompt}],
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
            ensure_google_response_ok(response, "Google AI generation")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to generate response from Google AI API: {exc}"
            ) from exc

        self._check_response_blocks(data)
        text = self._extract_text_from_response(data).strip()
        if not text:
            self._check_candidate_finish_reason(data, emitted_any=False)
        return text

    def analyze_image(self, image_path: Path, prompt: str, model: str) -> str:
        clean_model = normalize_google_model_id(model)
        if not clean_model:
            raise InfrastructureError("Google AI vision model name must not be empty.")

        headers = build_google_headers(self.api_key)
        image_part = encode_image_inline_part(image_path)
        payload = self._build_payload(
            parts=[{"text": prompt}, image_part],
            params=ModelParameters(num_ctx=4096, temperature=0.3, top_p=0.9, repeat_penalty=1.0),
            stop=None,
            format=None,
            think=False,
        )
        url = f"{self.base_url}/models/{clean_model}:generateContent"
        try:
            response = self._post_with_thinking_fallback(
                url=url, headers=headers, payload=payload, stream=False
            )
            ensure_google_response_ok(response, "Google AI vision analysis")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to analyze image via Google AI API: {exc}"
            ) from exc

        self._check_response_blocks(data)
        text = self._extract_text_from_response(data).strip()
        if not text:
            self._check_candidate_finish_reason(data, emitted_any=False)
        return text

    def list_model_catalog(self) -> tuple[list[str], list[str]]:
        headers = build_google_headers(self.api_key)
        text_models: list[str] = []
        image_models: list[str] = []
        page_token: str | None = None

        try:
            while True:
                params: dict[str, Any] = {"pageSize": 100}
                if page_token:
                    params["pageToken"] = page_token
                response = requests.get(
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
            response = requests.get(
                f"{self.base_url}/models",
                headers={"x-goog-api-key": self.api_key},
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
        if cache_key in self._MODEL_CTX_CACHE:
            return self._MODEL_CTX_CACHE[cache_key]

        try:
            response = requests.get(
                f"{self.base_url}/models/{clean_model}",
                headers={"x-goog-api-key": self.api_key},
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
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            stream=stream,
            timeout=self.request_timeout,
        )
        response.encoding = "utf-8"
        if (
            response.status_code == 400
            and "thinkingConfig" in (payload.get("generationConfig") or {})
            and "thinking" in (response.text or "").lower()
        ):
            response.close()
            fallback_payload = dict(payload)
            gen_cfg = dict(payload["generationConfig"])
            gen_cfg.pop("thinkingConfig", None)
            fallback_payload["generationConfig"] = gen_cfg
            response = requests.post(
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
        generation_config: dict[str, Any] = {
            "temperature": float(params.temperature),
            "topP": float(params.top_p),
        }
        if stop:
            clean_stops = [s for s in stop if isinstance(s, str) and s][:5]
            if clean_stops:
                generation_config["stopSequences"] = clean_stops

        if format == "json":
            generation_config["responseMimeType"] = "application/json"
        elif isinstance(format, dict):
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseJsonSchema"] = format

        if think is False:
            generation_config["thinkingConfig"] = {
                "thinkingLevel": "low",
                "includeThoughts": False,
            }
        elif think is True:
            generation_config["thinkingConfig"] = {
                "thinkingLevel": "high",
                "includeThoughts": False,
            }

        return {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
            "safetySettings": DEFAULT_GOOGLE_AI_SAFETY_SETTINGS,
        }

    @staticmethod
    def _extract_text_from_response(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ""
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        chunks: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if part.get("thought") is True:
                continue
            text = part.get("text")
            if text:
                chunks.append(str(text))
        return "".join(chunks)

    @staticmethod
    def _check_response_blocks(payload: dict[str, Any]) -> None:
        if "error" in payload and isinstance(payload["error"], dict):
            msg = payload["error"].get("message") or str(payload["error"])
            raise InfrastructureError(f"Google AI generation error: {msg}")
        feedback = payload.get("promptFeedback")
        if isinstance(feedback, dict):
            block_reason = feedback.get("blockReason")
            if block_reason:
                raise InfrastructureError(
                    f"Google AI blocked the request ({block_reason})."
                )

    @staticmethod
    def _check_candidate_finish_reason(
        payload: dict[str, Any],
        emitted_any: bool,
    ) -> None:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return
        first = candidates[0] if isinstance(candidates[0], dict) else {}
        finish_reason = str(first.get("finishReason") or "")
        if not emitted_any and finish_reason in (
            "SAFETY",
            "PROHIBITED_CONTENT",
            "SPII",
            "BLOCKLIST",
            "RECITATION",
        ):
            raise InfrastructureError(
                f"Google AI blocked the response (finishReason={finish_reason})."
            )
