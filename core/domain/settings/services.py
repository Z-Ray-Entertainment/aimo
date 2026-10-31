from urllib.parse import urlparse

from domain.settings.exceptions import (
    InvalidServiceUrlError,
    InvalidTaskModelError,
)
from domain.settings.models import (
    ModelParameters,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
)
from shared.config import Config


class SettingsService:
    def get_default_settings(self) -> ServiceSettings:
        return ServiceSettings(
            id=1,
            ollama_url=Config.DEFAULT_OLLAMA_URL,
            comfyui_url=Config.DEFAULT_COMFYUI_URL,
            searxng_url=Config.DEFAULT_SEARXNG_URL,
            searxng_enabled=False,
            tasks=TaskAssignment(),
            params=ModelParameters(),
            prompts=SystemPrompts(),
        )

    def update_service_urls(
        self,
        settings: ServiceSettings,
        ollama_url: str,
        comfyui_url: str,
        searxng_url: str,
        searxng_enabled: bool = False,
    ) -> ServiceSettings:
        settings.ollama_url = self._validate_url("ollama_url", ollama_url)
        settings.comfyui_url = self._validate_url("comfyui_url", comfyui_url)
        settings.searxng_url = self._validate_url("searxng_url", searxng_url)
        settings.searxng_enabled = bool(searxng_enabled)
        return settings

    def update_task_models(
        self,
        settings: ServiceSettings,
        roleplay_model: str,
        memory_model: str,
        assistant_model: str,
        vision_model: str,
        classification_model: str | None = None,
    ) -> ServiceSettings:
        cleaned_roleplay = self._validate_model_name("roleplay_model", roleplay_model)
        cleaned_memory = self._validate_model_name("memory_model", memory_model)
        cleaned_assistant = self._validate_model_name("assistant_model", assistant_model)
        cleaned_vision = self._validate_model_name("vision_model", vision_model)
        cleaned_classification = self._validate_model_name(
            "classification_model",
            classification_model or cleaned_roleplay,
        )

        settings.tasks = TaskAssignment(
            roleplay_model=cleaned_roleplay,
            memory_model=cleaned_memory,
            assistant_model=cleaned_assistant,
            vision_model=cleaned_vision,
            classification_model=cleaned_classification,
        )
        return settings

    def update_parameters(
        self,
        settings: ServiceSettings,
        num_ctx: int,
        temperature: float,
        top_p: float,
        repeat_penalty: float,
    ) -> ServiceSettings:
        settings.params = ModelParameters(
            num_ctx=num_ctx,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
        )
        return settings

    def update_system_prompts(
        self,
        settings: ServiceSettings,
        roleplay_prompt: str,
        memory_prompt: str,
        diffuser_prompt: str,
        sparkle_assistant_prompt: str,
        vision_persona_prompt: str | None = None,
    ) -> ServiceSettings:
        resolved_vision_prompt = (
            settings.prompts.vision_persona_prompt
            if vision_persona_prompt is None
            else vision_persona_prompt.strip()
        )
        settings.prompts = SystemPrompts(
            roleplay_prompt=roleplay_prompt.strip() if isinstance(roleplay_prompt, str) else "",
            memory_prompt=memory_prompt.strip() if isinstance(memory_prompt, str) else "",
            diffuser_prompt=diffuser_prompt.strip() if isinstance(diffuser_prompt, str) else "",
            sparkle_assistant_prompt=(
                sparkle_assistant_prompt.strip()
                if isinstance(sparkle_assistant_prompt, str)
                else ""
            ),
            vision_persona_prompt=resolved_vision_prompt,
        )
        return settings

    @staticmethod
    def _validate_url(field_name: str, raw_url: str) -> str:
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise InvalidServiceUrlError(f"Service URL '{field_name}' must not be empty.")
        cleaned = raw_url.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InvalidServiceUrlError(
                f"Service URL '{field_name}' must be a valid HTTP/HTTPS URL: '{raw_url}'."
            )
        return cleaned

    @staticmethod
    def _validate_model_name(field_name: str, model_name: str) -> str:
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidTaskModelError(f"Task model '{field_name}' must not be empty.")
        return model_name.strip()
