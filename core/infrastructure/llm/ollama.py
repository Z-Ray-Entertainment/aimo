import base64
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import requests

from domain.settings.models import ModelParameters
from infrastructure.llm.interface import LLMProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class OllamaLLMProvider(LLMProvider):
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
        self, prompt: str, model: str, params: ModelParameters
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": self._build_options(params),
        }
        try:
            with requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.request_timeout,
            ) as response:
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

    def generate(self, prompt: str, model: str, params: ModelParameters) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": self._build_options(params),
        }
        try:
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

    def classify(self, text: str, candidates: list[str], model: str) -> str:
        cleaned_candidates = [c.strip() for c in candidates if c.strip()]
        if not cleaned_candidates:
            raise InfrastructureError(
                "Classification requires at least one non-empty candidate label."
            )

        candidates_str = ", ".join(cleaned_candidates)
        prompt = (
            "Classify the following narrative passage by choosing strictly one label "
            f"from the valid candidates: [{candidates_str}].\n"
            "Respond with ONLY the exact candidate label and nothing else.\n\n"
            f"Passage:\n{text}\n\n"
            "Selected label:"
        )
        classification_params = ModelParameters(
            num_ctx=2048,
            temperature=0.0,
            top_p=0.9,
            repeat_penalty=1.0,
        )
        raw_output = self.generate(
            prompt=prompt, model=model, params=classification_params
        )
        return self._match_candidate(raw_output, cleaned_candidates)

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

    @staticmethod
    def _build_options(params: ModelParameters) -> dict[str, int | float]:
        return {
            "num_ctx": params.num_ctx,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "repeat_penalty": params.repeat_penalty,
        }

    @staticmethod
    def _ensure_ok(response: requests.Response, context: str) -> None:
        if response.status_code >= 400:
            detail = response.text.strip()
            raise InfrastructureError(
                f"{context} failed with HTTP {response.status_code}: {detail}"
            )

    @staticmethod
    def _match_candidate(raw_output: str, candidates: list[str]) -> str:
        normalized_output = raw_output.strip().strip("`'\".,:;!?()[]{}").lower()
        lower_map = {candidate.lower(): candidate for candidate in candidates}

        if normalized_output in lower_map:
            return lower_map[normalized_output]

        for candidate in candidates:
            pattern = rf"\b{re.escape(candidate.lower())}\b"
            if re.search(pattern, normalized_output):
                return candidate

        for candidate in candidates:
            if candidate.lower() in normalized_output:
                return candidate

        return candidates[0]
