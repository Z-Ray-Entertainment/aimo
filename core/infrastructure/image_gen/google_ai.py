import base64
from io import BytesIO
from pathlib import Path
import time
from typing import Any, ClassVar

from PIL import Image
import requests

from domain.settings.models import ServiceSettings
from domain.settings.services import SettingsService
from infrastructure.google_ai_common import (
    DEFAULT_GOOGLE_AI_SAFETY_SETTINGS,
    build_google_headers,
    encode_image_inline_part,
    ensure_google_response_ok,
    normalize_google_model_id,
)
from infrastructure.image_gen.interface import ImageGenProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class GoogleAIImageGenProvider(ImageGenProvider):
    PROVIDER_ID: ClassVar[str] = "google_ai"
    DISPLAY_NAME: ClassVar[str] = "Google AI Image"
    REQUIRES_LLM_BACKEND: ClassVar[str | None] = "google_ai"
    RECOMMENDED_MODEL: ClassVar[str | None] = "gemini-3.1-flash-image-preview"
    DEFAULT_BASE_URL: ClassVar[str] = Config.GOOGLE_AI_BASE_URL

    _HEALTH_CACHE: dict[tuple[str, str], tuple[float, bool]] = {}
    _HEALTH_TTL_SECONDS: float = 60.0
    _CANCELLED_TASKS: set[str] = set()

    @classmethod
    def get_default_config(cls) -> dict[str, str]:
        return {"model": cls.RECOMMENDED_MODEL or ""}

    @classmethod
    def validate_active_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        raw_model = (
            (submitted.get("model") or "").strip()
            or (existing.get("model") or "").strip()
            or (cls.RECOMMENDED_MODEL or "")
        )
        return {"model": SettingsService.validate_model_name("google_ai_image_model", raw_model)}

    @classmethod
    def validate_inactive_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
    ) -> dict[str, str]:
        raw_model = (
            (submitted.get("model") or "").strip()
            or (existing.get("model") or "").strip()
            or (cls.RECOMMENDED_MODEL or "")
        )
        return {"model": raw_model}

    @classmethod
    def from_settings(cls, settings: ServiceSettings) -> "GoogleAIImageGenProvider":
        llm_cfg = settings.get_llm_config(cls.REQUIRES_LLM_BACKEND)
        api_key = llm_cfg.get("api_key") or Config.DEFAULT_GOOGLE_AI_API_KEY
        img_cfg = settings.get_image_gen_config(cls.PROVIDER_ID)
        model = img_cfg.get("model") or (cls.RECOMMENDED_MODEL or "")
        return cls(api_key=api_key, model=model, base_url=cls.DEFAULT_BASE_URL)

    def build_scene_prompt_instruction(
        self,
        diffuser_prompt: str,
        character_summary: str,
        persona_summary: str,
        location_desc: str,
        scene_text: str,
    ) -> str:
        return (
            "Write a vivid, cohesive, natural-language English visual scene description "
            "(no Stable Diffusion comma tags, weights, or meta-commentary) capturing the atmosphere, "
            "lighting, framing, clothing, expressions, and environment for a 16:9 cinematic illustration "
            "of this roleplay moment.\n\n"
            f"Character: {character_summary}\n"
            f"Player Persona Appearance: {persona_summary}\n"
            f"Location: {location_desc}\n"
            f"Recent Scene:\n{scene_text}"
        )

    def __init__(
        self,
        api_key: str,
        model: str = RECOMMENDED_MODEL or "",
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: tuple[float, float] = (10.0, 120.0),
    ) -> None:
        self.api_key: str = (api_key or "").strip()
        self.model: str = normalize_google_model_id(
            model or (self.RECOMMENDED_MODEL or "")
        )
        self.base_url: str = base_url.strip().rstrip("/")
        self.request_timeout: tuple[float, float] = request_timeout

    def generate_image(
        self,
        prompt: str,
        reference_images: list[Path],
        negative_prompt: str,
        output_path: Path,
    ) -> Path:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise InfrastructureError("Image generation prompt must not be empty.")
        if not self.model:
            raise InfrastructureError("Google AI image model must not be empty.")

        headers = build_google_headers(self.api_key)
        instruction_lines = [cleaned_prompt]
        if reference_images:
            instruction_lines.append(
                "Use the attached reference images to stay consistent with character appearance, "
                "player appearance, and location atmosphere."
            )
        if negative_prompt and negative_prompt.strip():
            instruction_lines.append(f"Avoid: {negative_prompt.strip()}")

        parts: list[dict[str, Any]] = [{"text": "\n".join(instruction_lines)}]
        for ref_path in reference_images:
            resolved_ref = Path(ref_path).resolve()
            if resolved_ref.is_file():
                parts.append(encode_image_inline_part(resolved_ref))

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": "16:9",
                },
            },
            "safetySettings": DEFAULT_GOOGLE_AI_SAFETY_SETTINGS,
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
            )
            if response.status_code == 400 and "imageConfig" in (response.text or ""):
                fallback_payload = dict(payload)
                fallback_gen = dict(payload["generationConfig"])
                fallback_gen.pop("imageConfig", None)
                fallback_payload["generationConfig"] = fallback_gen
                response = requests.post(
                    url,
                    headers=headers,
                    json=fallback_payload,
                    timeout=self.request_timeout,
                )
            ensure_google_response_ok(response, "Google AI image generation")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to generate image via Google AI API: {exc}"
            ) from exc

        image_bytes = self._extract_image_bytes(data)
        if not image_bytes:
            raise InfrastructureError(
                "Google AI image generation returned no image data."
            )

        target_path = Path(output_path).resolve()
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(BytesIO(image_bytes)) as img:
                img.save(target_path, format="PNG")
        except Exception as exc:
            raise InfrastructureError(
                f"Failed to save Google AI generated image to '{target_path}': {exc}"
            ) from exc

        return target_path

    def cancel_generation(self, task_id: str) -> None:
        cleaned = task_id.strip() if isinstance(task_id, str) else ""
        if cleaned:
            self._CANCELLED_TASKS.add(cleaned)

    def check_health(self) -> bool:
        if not self.api_key or not self.model:
            return False
        cache_key = (f"{self.base_url}:{hash(self.api_key)}", self.model)
        now = time.monotonic()
        cached = self._HEALTH_CACHE.get(cache_key)
        if cached and (now - cached[0]) < self._HEALTH_TTL_SECONDS:
            return cached[1]

        healthy = False
        try:
            response = requests.get(
                f"{self.base_url}/models/{self.model}",
                headers={"x-goog-api-key": self.api_key},
                timeout=(3.0, 4.0),
            )
            healthy = response.status_code == 200
        except requests.RequestException:
            healthy = False

        self._HEALTH_CACHE[cache_key] = (now, healthy)
        return healthy

    @staticmethod
    def _extract_image_bytes(payload: dict[str, Any]) -> bytes | None:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline, dict) and inline.get("data"):
                    try:
                        return base64.b64decode(inline["data"])
                    except Exception:
                        return None
        return None
