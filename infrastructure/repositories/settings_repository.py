from domain.settings.models import (
    ModelParameters,
    ServiceSettings,
    SystemPrompts,
    TaskAssignment,
)
from domain.settings.services import SettingsService
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import SettingsORM


class SettingsRepository:
    def __init__(self) -> None:
        self._service = SettingsService()

    def get_settings(self) -> ServiceSettings:
        with get_db_session() as session:
            orm_settings = session.get(SettingsORM, 1)
            if orm_settings is None:
                defaults = self._service.get_default_settings()
                orm_settings = self._to_orm(defaults)
                session.add(orm_settings)
                session.flush()
            return self._to_entity(orm_settings)

    def save_settings(self, settings: ServiceSettings) -> ServiceSettings:
        with get_db_session() as session:
            orm_settings = session.get(SettingsORM, 1)
            if orm_settings is None:
                orm_settings = self._to_orm(settings)
                session.add(orm_settings)
            else:
                orm_settings.ollama_url = settings.ollama_url
                orm_settings.comfyui_url = settings.comfyui_url
                orm_settings.searxng_url = settings.searxng_url
                orm_settings.searxng_enabled = settings.searxng_enabled

                orm_settings.roleplay_model = settings.tasks.roleplay_model
                orm_settings.memory_model = settings.tasks.memory_model
                orm_settings.assistant_model = settings.tasks.assistant_model
                orm_settings.vision_model = settings.tasks.vision_model

                orm_settings.num_ctx = settings.params.num_ctx
                orm_settings.temperature = settings.params.temperature
                orm_settings.top_p = settings.params.top_p
                orm_settings.repeat_penalty = settings.params.repeat_penalty

                orm_settings.roleplay_prompt = settings.prompts.roleplay_prompt
                orm_settings.memory_prompt = settings.prompts.memory_prompt
                orm_settings.diffuser_prompt = settings.prompts.diffuser_prompt
                orm_settings.sparkle_assistant_prompt = (
                    settings.prompts.sparkle_assistant_prompt
                )
                orm_settings.vision_persona_prompt = (
                    settings.prompts.vision_persona_prompt
                )
            session.flush()
            return self._to_entity(orm_settings)

    @staticmethod
    def _to_orm(settings: ServiceSettings) -> SettingsORM:
        return SettingsORM(
            id=1,
            ollama_url=settings.ollama_url,
            comfyui_url=settings.comfyui_url,
            searxng_url=settings.searxng_url,
            searxng_enabled=settings.searxng_enabled,
            roleplay_model=settings.tasks.roleplay_model,
            memory_model=settings.tasks.memory_model,
            assistant_model=settings.tasks.assistant_model,
            vision_model=settings.tasks.vision_model,
            num_ctx=settings.params.num_ctx,
            temperature=settings.params.temperature,
            top_p=settings.params.top_p,
            repeat_penalty=settings.params.repeat_penalty,
            roleplay_prompt=settings.prompts.roleplay_prompt,
            memory_prompt=settings.prompts.memory_prompt,
            diffuser_prompt=settings.prompts.diffuser_prompt,
            sparkle_assistant_prompt=settings.prompts.sparkle_assistant_prompt,
            vision_persona_prompt=settings.prompts.vision_persona_prompt,
        )

    @staticmethod
    def _to_entity(orm_settings: SettingsORM) -> ServiceSettings:
        return ServiceSettings(
            id=orm_settings.id,
            ollama_url=orm_settings.ollama_url,
            comfyui_url=orm_settings.comfyui_url,
            searxng_url=orm_settings.searxng_url,
            searxng_enabled=orm_settings.searxng_enabled,
            tasks=TaskAssignment(
                roleplay_model=orm_settings.roleplay_model,
                memory_model=orm_settings.memory_model,
                assistant_model=orm_settings.assistant_model,
                vision_model=orm_settings.vision_model,
            ),
            params=ModelParameters(
                num_ctx=orm_settings.num_ctx,
                temperature=orm_settings.temperature,
                top_p=orm_settings.top_p,
                repeat_penalty=orm_settings.repeat_penalty,
            ),
            prompts=SystemPrompts(
                roleplay_prompt=orm_settings.roleplay_prompt,
                memory_prompt=orm_settings.memory_prompt,
                diffuser_prompt=orm_settings.diffuser_prompt,
                sparkle_assistant_prompt=orm_settings.sparkle_assistant_prompt,
                vision_persona_prompt=orm_settings.vision_persona_prompt,
            ),
        )
