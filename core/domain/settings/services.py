from urllib.parse import urlparse

from domain.settings.exceptions import (
    InvalidServiceCredentialsError,
    InvalidServiceUrlError,
    InvalidTaskModelError,
)
from domain.settings.models import (
    ModelParameters,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
)


class SettingsService:
    def get_default_settings(
        self,
        llm_backend: str = "",
        image_gen_backend: str = "",
        search_backend: str = "",
        tasks: TaskAssignment | None = None,
    ) -> ServiceSettings:
        return ServiceSettings(
            id=1,
            llm_backend=llm_backend.strip().lower(),
            image_gen_backend=image_gen_backend.strip().lower(),
            search_backend=search_backend.strip().lower(),
            tasks=tasks or TaskAssignment(),
            params=ModelParameters(),
            prompts=SystemPrompts(),
            default_backdrop_path=None,
        )

    def update_task_models(
        self,
        settings: ServiceSettings,
        roleplay_model: str,
        memory_model: str,
        assistant_model: str,
        vision_model: str,
        classification_model: str | None = None,
    ) -> ServiceSettings:
        cleaned_roleplay = self.validate_model_name("roleplay_model", roleplay_model)
        cleaned_memory = self.validate_model_name("memory_model", memory_model)
        cleaned_assistant = self.validate_model_name("assistant_model", assistant_model)
        cleaned_vision = self.validate_model_name("vision_model", vision_model)
        cleaned_classification = self.validate_model_name(
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

    def apply_task_model_map(
        self,
        settings: ServiceSettings,
        recommended_by_role: dict[str, str],
    ) -> ServiceSettings:
        roleplay = recommended_by_role.get("roleplay", "")
        return self.update_task_models(
            settings=settings,
            roleplay_model=roleplay,
            memory_model=recommended_by_role.get("memory", roleplay),
            assistant_model=recommended_by_role.get("assistant", roleplay),
            vision_model=recommended_by_role.get("vision", roleplay),
            classification_model=recommended_by_role.get("classification", roleplay),
        )

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
        dialogue_author_prompt: str | None = None,
    ) -> ServiceSettings:
        resolved_vision_prompt = (
            settings.prompts.vision_persona_prompt
            if vision_persona_prompt is None
            else vision_persona_prompt.strip()
        )
        resolved_dialogue_prompt = (
            settings.prompts.dialogue_author_prompt
            if dialogue_author_prompt is None
            else dialogue_author_prompt.strip()
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
            dialogue_author_prompt=resolved_dialogue_prompt,
        )
        return settings

    def update_default_backdrop(
        self,
        settings: ServiceSettings,
        backdrop_path: str | None,
    ) -> ServiceSettings:
        cleaned = (
            backdrop_path.strip()
            if isinstance(backdrop_path, str) and backdrop_path.strip()
            else None
        )
        settings.default_backdrop_path = cleaned
        return settings

    @staticmethod
    def validate_url(field_name: str, raw_url: str) -> str:
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
    def validate_secret(field_name: str, raw_secret: str) -> str:
        if not isinstance(raw_secret, str) or not raw_secret.strip():
            raise InvalidServiceCredentialsError(
                f"Service credential '{field_name}' must not be empty."
            )
        cleaned = raw_secret.strip()
        if any(ch.isspace() for ch in cleaned):
            raise InvalidServiceCredentialsError(
                f"Service credential '{field_name}' must not contain whitespace."
            )
        return cleaned

    @staticmethod
    def validate_model_name(field_name: str, model_name: str) -> str:
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidTaskModelError(f"Task model '{field_name}' must not be empty.")
        return model_name.strip()
