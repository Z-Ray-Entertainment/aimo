from domain.settings.models import ServiceSettings
from domain.settings.services import SettingsService
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.disabled import DisabledImageGenProvider
from infrastructure.image_gen.factory import (
    IMAGE_GEN_PROVIDER_CLASSES,
    get_image_gen_provider_class,
)
from infrastructure.llm.factory import LLM_PROVIDER_CLASSES, get_llm_provider_class
from infrastructure.llm.ollama import OllamaLLMProvider
from infrastructure.search.factory import (
    SEARCH_PROVIDER_CLASSES,
    get_search_provider_class,
)
from infrastructure.search.stub import DisabledSearchProvider
from shared.config import Config


class ProviderRegistry:
    """Infrastructure coordinator binding generic domain settings to concrete providers."""

    @staticmethod
    def get_recommended_models_by_backend() -> dict[str, dict[str, dict[str, str]]]:
        return {
            provider_id: cls.get_recommended_models()
            for provider_id, cls in LLM_PROVIDER_CLASSES.items()
        }

    @staticmethod
    def get_recommended_task_models_by_backend() -> dict[str, dict[str, str]]:
        return {
            provider_id: cls.get_recommended_task_models()
            for provider_id, cls in LLM_PROVIDER_CLASSES.items()
        }

    @staticmethod
    def build_default_settings() -> ServiceSettings:
        raw_default_llm = (Config.DEFAULT_LLM_BACKEND or "").strip().lower()
        default_llm = (
            raw_default_llm
            if raw_default_llm in LLM_PROVIDER_CLASSES
            else OllamaLLMProvider.PROVIDER_ID
        )
        llm_cls = get_llm_provider_class(default_llm)

        default_img = DisabledImageGenProvider.PROVIDER_ID
        for img_id, img_cls in IMAGE_GEN_PROVIDER_CLASSES.items():
            if img_cls.REQUIRES_LLM_BACKEND == default_llm:
                default_img = img_id
                break
        if default_img == DisabledImageGenProvider.PROVIDER_ID:
            default_img = ComfyUIImageGenProvider.PROVIDER_ID

        settings = SettingsService().get_default_settings(
            llm_backend=default_llm,
            image_gen_backend=default_img,
            search_backend=DisabledSearchProvider.PROVIDER_ID,
            tasks=llm_cls.get_recommended_task_assignment(),
        )
        for pid, cls in LLM_PROVIDER_CLASSES.items():
            settings.set_llm_config(pid, cls.get_default_config())
        for pid, cls in IMAGE_GEN_PROVIDER_CLASSES.items():
            settings.set_image_gen_config(pid, cls.get_default_config())
        for pid, cls in SEARCH_PROVIDER_CLASSES.items():
            settings.set_search_config(pid, cls.get_default_config())
        return settings

    @staticmethod
    def update_backend_configuration(
        settings: ServiceSettings,
        llm_backend: str,
        llm_configs: dict[str, dict[str, str]] | None = None,
        clear_llm_secrets: set[str] | None = None,
        image_gen_backend: str | None = None,
        image_gen_configs: dict[str, dict[str, str]] | None = None,
        search_backend: str | None = None,
        search_configs: dict[str, dict[str, str]] | None = None,
    ) -> ServiceSettings:
        previous_llm = settings.llm_backend
        llm_cls = get_llm_provider_class(llm_backend)
        resolved_llm = llm_cls.PROVIDER_ID

        submitted_llm_map = llm_configs or {}
        clear_set = {b.strip().lower() for b in (clear_llm_secrets or set())}
        for pid, cls in LLM_PROVIDER_CLASSES.items():
            submitted = submitted_llm_map.get(pid, {})
            existing = settings.get_llm_config(pid) or cls.get_default_config()
            if pid == resolved_llm:
                validated = cls.validate_active_config(
                    submitted, existing, clear_secret=(pid in clear_set)
                )
            else:
                validated = cls.validate_inactive_config(
                    submitted, existing, clear_secret=(pid in clear_set)
                )
            settings.set_llm_config(pid, validated)

        target_img_id = image_gen_backend or settings.image_gen_backend or DisabledImageGenProvider.PROVIDER_ID
        img_cls = get_image_gen_provider_class(target_img_id)
        if (
            img_cls.REQUIRES_LLM_BACKEND is not None
            and img_cls.REQUIRES_LLM_BACKEND != resolved_llm
        ):
            fallback_comfy = (
                (image_gen_configs or {}).get(ComfyUIImageGenProvider.PROVIDER_ID, {}).get("base_url")
                or settings.get_image_gen_config(ComfyUIImageGenProvider.PROVIDER_ID).get("base_url")
            )
            target_img_id = (
                ComfyUIImageGenProvider.PROVIDER_ID
                if fallback_comfy and fallback_comfy.strip()
                else DisabledImageGenProvider.PROVIDER_ID
            )
            img_cls = get_image_gen_provider_class(target_img_id)
        resolved_img = img_cls.PROVIDER_ID

        submitted_img_map = image_gen_configs or {}
        for pid, cls in IMAGE_GEN_PROVIDER_CLASSES.items():
            submitted = submitted_img_map.get(pid, {})
            existing = settings.get_image_gen_config(pid) or cls.get_default_config()
            if pid == resolved_img:
                validated = cls.validate_active_config(submitted, existing)
            else:
                validated = cls.validate_inactive_config(submitted, existing)
            settings.set_image_gen_config(pid, validated)

        target_search_id = search_backend or settings.search_backend or DisabledSearchProvider.PROVIDER_ID
        search_cls = get_search_provider_class(target_search_id)
        if (
            search_cls.REQUIRES_LLM_BACKEND is not None
            and search_cls.REQUIRES_LLM_BACKEND != resolved_llm
        ):
            target_search_id = DisabledSearchProvider.PROVIDER_ID
            search_cls = get_search_provider_class(target_search_id)
        resolved_search = search_cls.PROVIDER_ID

        submitted_search_map = search_configs or {}
        for pid, cls in SEARCH_PROVIDER_CLASSES.items():
            submitted = submitted_search_map.get(pid, {})
            existing = settings.get_search_config(pid) or cls.get_default_config()
            if pid == resolved_search:
                validated = cls.validate_active_config(submitted, existing)
            else:
                validated = cls.validate_inactive_config(submitted, existing)
            settings.set_search_config(pid, validated)

        settings.llm_backend = resolved_llm
        settings.image_gen_backend = resolved_img
        settings.search_backend = resolved_search

        if previous_llm != resolved_llm:
            ProviderRegistry.reconcile_task_models(settings, previous_backend=previous_llm)

        return settings

    @staticmethod
    def apply_recommended_models(settings: ServiceSettings) -> ServiceSettings:
        llm_cls = get_llm_provider_class(settings.llm_backend)
        SettingsService().apply_task_model_map(
            settings, llm_cls.get_recommended_task_models()
        )
        img_cls = get_image_gen_provider_class(settings.image_gen_backend)
        rec_img = img_cls.get_recommended_model()
        if rec_img:
            cfg = settings.get_image_gen_config(img_cls.PROVIDER_ID)
            if not cfg.get("model"):
                cfg["model"] = rec_img
                settings.set_image_gen_config(img_cls.PROVIDER_ID, cfg)
        return settings

    @staticmethod
    def reconcile_task_models(
        settings: ServiceSettings,
        previous_backend: str | None = None,
    ) -> ServiceSettings:
        target_cls = get_llm_provider_class(settings.llm_backend)
        rec = target_cls.get_recommended_task_models()
        prev_models: set[str] = set()
        if previous_backend and previous_backend != target_cls.PROVIDER_ID:
            prev_cls = LLM_PROVIDER_CLASSES.get(previous_backend)
            if prev_cls is not None:
                prev_models = set(prev_cls.get_recommended_task_models().values())

        def _pick(current: str, role: str) -> str:
            cleaned = (current or "").strip()
            if not cleaned or not target_cls.is_model_compatible(cleaned):
                return rec[role]
            if cleaned in prev_models:
                return rec[role]
            return cleaned

        return SettingsService().update_task_models(
            settings=settings,
            roleplay_model=_pick(settings.tasks.roleplay_model, "roleplay"),
            memory_model=_pick(settings.tasks.memory_model, "memory"),
            assistant_model=_pick(settings.tasks.assistant_model, "assistant"),
            vision_model=_pick(settings.tasks.vision_model, "vision"),
            classification_model=_pick(settings.tasks.classification_model, "classification"),
        )
