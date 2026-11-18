import base64
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import requests

from domain.settings.models import ModelParameters
from infrastructure.llm.base import BaseLLMProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(
        self,
        base_url: str = Config.DEFAULT_OLLAMA_URL,
        request_timeout: tuple[float, float] = (10.0, 120.0),
        pull_timeout: tuple[float, float] = (10.0, 600.0),
    ) -> None:
        self.base_url: str = base_url.strip().rstrip("/")
        self.request_timeout: tuple[float, float] = request_timeout
        self.pull_timeout: tuple[float, float] = pull_timeout

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
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.request_timeout,
            )
            if response.status_code == 400 and think is not None and "think" in response.text.lower():
                payload.pop("think", None)
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    stream=True,
                    timeout=self.request_timeout,
                )
            with response:
                self._ensure_ok(response, "Ollama streaming generation")
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        raise InfrastructureError(
                            f"Invalid JSON chunk received from Ollama stream: {raw_line}"
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
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if format:
            payload["format"] = format
        if think is not None:
            payload["think"] = think
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.request_timeout,
            )
            if response.status_code == 400 and think is not None and "think" in response.text.lower():
                payload.pop("think", None)
                response = requests.post(
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
        resolved_path = Path(image_path).resolve()
        if not resolved_path.is_file():
            raise InfrastructureError(
                f"Image file for vision analysis does not exist: '{resolved_path}'."
            )

        try:
            encoded_image = base64.b64encode(resolved_path.read_bytes()).decode("ascii")
        except OSError as exc:
            raise InfrastructureError(
                f"Failed to read image file '{resolved_path}': {exc}"
            ) from exc

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False,
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.request_timeout,
            )
            self._ensure_ok(response, "Ollama vision analysis")
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
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.request_timeout,
            )
            self._ensure_ok(response, "Ollama list models")
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
            with requests.post(
                f"{self.base_url}/api/pull",
                json=payload,
                stream=True,
                timeout=self.pull_timeout,
            ) as response:
                self._ensure_ok(response, f"Ollama pull model '{cleaned_name}'")
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        raise InfrastructureError(
                            f"Invalid JSON status received during model pull: {raw_line}"
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
            response = requests.delete(
                f"{self.base_url}/api/delete",
                json={"name": cleaned_name},
                timeout=self.request_timeout,
            )
            if response.status_code == 404:
                return False
            self._ensure_ok(response, f"Ollama delete model '{cleaned_name}'")
            return True
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to delete model '{cleaned_name}' from Ollama at '{self.base_url}': {exc}"
            ) from exc

    def check_health(self) -> bool:
        try:
            response = requests.get(
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
        if cache_key in self._MODEL_CTX_CACHE:
            return self._MODEL_CTX_CACHE[cache_key]

        try:
            response = requests.post(
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
    def _build_options(params: ModelParameters) -> dict[str, int | float]:
        return {
            "num_ctx": params.num_ctx,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "repeat_penalty": params.repeat_penalty,
        }
