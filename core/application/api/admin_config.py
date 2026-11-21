from __future__ import annotations

from flask import Blueprint, jsonify

from application.api.auth import require_permission
from application.api.helpers import parse_request_payload
from domain.permissions.models import FunctionPermission
from domain.settings.services import SettingsService
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider
from infrastructure.provider_registry import ProviderRegistry
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.translation.worker import trigger_translation_sync
from shared.exceptions import AimoError

api_admin_config_bp = Blueprint("api_admin_config", __name__, url_prefix="/api/admin")


def _group_recommended_models(role_models: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[str]] = {}
    for info in role_models.values():
        model_id = info.get("model", "")
        role_name = info.get("role_name", "")
        if model_id:
            grouped.setdefault(model_id, []).append(role_name)
    return [{"model": model_id, "roles": roles} for model_id, roles in grouped.items()]


@api_admin_config_bp.route("/services", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_services_config():
    settings = SettingsRepository().get_settings()
    ollama_rec = OllamaLLMProvider.get_recommended_models()
    return jsonify(
        {
            "llm_backend": settings.llm_backend,
            "image_gen_backend": settings.image_gen_backend,
            "search_backend": settings.search_backend,
            "llm_configs": settings.llm_configs,
            "image_gen_configs": settings.image_gen_configs,
            "search_configs": settings.search_configs,
            "tasks": {
                "roleplay_model": settings.tasks.roleplay_model,
                "memory_model": settings.tasks.memory_model,
                "assistant_model": settings.tasks.assistant_model,
                "vision_model": settings.tasks.vision_model,
                "classification_model": settings.tasks.classification_model,
            },
            "params": {
                "num_ctx": settings.params.num_ctx,
                "temperature": settings.params.temperature,
                "top_p": settings.params.top_p,
                "repeat_penalty": settings.params.repeat_penalty,
                "max_tokens": settings.params.max_tokens,
            },
            "ollama_grouped_recommended": _group_recommended_models(ollama_rec),
            "ollama_unique_models": OllamaLLMProvider.get_unique_recommended_models(),
            "google_recommended_models": GoogleAILLMProvider.get_recommended_models(),
            "recommended_by_backend": ProviderRegistry.get_recommended_task_models_by_backend(),
            "recommended_google_image_model": GoogleAIImageGenProvider.get_recommended_model() or "",
        }
    )


@api_admin_config_bp.route("/services", methods=["PUT"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def update_services_config():
    data = parse_request_payload()
    settings_repo = SettingsRepository()
    settings = settings_repo.get_settings()
    settings_service = SettingsService()

    try:
        ProviderRegistry.update_backend_configuration(
            settings,
            llm_backend=str(data.get("llm_backend") or settings.llm_backend),
            llm_configs=data.get("llm_configs") if isinstance(data.get("llm_configs"), dict) else None,
            clear_llm_secrets=set(data.get("clear_llm_secrets") or []),
            image_gen_backend=data.get("image_gen_backend"),
            image_gen_configs=data.get("image_gen_configs") if isinstance(data.get("image_gen_configs"), dict) else None,
            search_backend=data.get("search_backend"),
            search_configs=data.get("search_configs") if isinstance(data.get("search_configs"), dict) else None,
        )
        if isinstance(data.get("tasks"), dict):
            settings_service.apply_task_model_map(settings, data["tasks"])
        if isinstance(data.get("params"), dict):
            p = data["params"]
            settings_service.update_parameters(
                settings,
                num_ctx=int(p.get("num_ctx", settings.params.num_ctx)),
                temperature=float(p.get("temperature", settings.params.temperature)),
                top_p=float(p.get("top_p", settings.params.top_p)),
                repeat_penalty=float(p.get("repeat_penalty", settings.params.repeat_penalty)),
                max_tokens=int(p["max_tokens"]) if p.get("max_tokens") is not None else settings.params.max_tokens,
            )
        settings_repo.save_settings(settings)
        return jsonify({"saved": True})
    except (AimoError, ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_admin_config_bp.route("/prompts", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_prompts_config():
    from domain.settings.models import PROMPT_KEYS, SystemPrompts, get_default_prompt, is_default_prompt
    from domain.translation.models import SUPPORTED_LANGUAGES
    from infrastructure.llm.factory import get_llm_provider_class

    settings = SettingsRepository().get_settings()
    defaults = SystemPrompts()
    trans_repo = TranslationRepository()

    prompt_variants: dict[str, dict[str, dict]] = {}
    default_prompt_variants: dict[str, dict[str, dict]] = {}
    for key in PROMPT_KEYS:
        default_map = {
            lang: {
                "content": get_default_prompt(key, lang),
                "text": get_default_prompt(key, lang),
                "is_outdated": False,
                "outdated": False,
            }
            for lang in SUPPORTED_LANGUAGES
        }
        default_prompt_variants[key] = default_map
        current_val = getattr(settings.prompts, key, "")
        if is_default_prompt(key, current_val):
            prompt_variants[key] = default_map
        else:
            stored = trans_repo.get_field_translations("system_prompt", 1, key)
            if "en" not in stored and current_val:
                stored["en"] = {"content": current_val, "text": current_val, "is_outdated": False, "outdated": False}
            prompt_variants[key] = stored

    is_cloud_llm = get_llm_provider_class(settings.llm_backend).is_cloud_provider()
    return jsonify(
        {
            "prompts": {
                "roleplay_prompt": settings.prompts.roleplay_prompt,
                "memory_prompt": settings.prompts.memory_prompt,
                "dialogue_author_prompt": settings.prompts.dialogue_author_prompt,
                "diffuser_prompt": settings.prompts.diffuser_prompt,
                "sparkle_assistant_prompt": settings.prompts.sparkle_assistant_prompt,
                "vision_persona_prompt": settings.prompts.vision_persona_prompt,
            },
            "defaults": {
                "roleplay_prompt": defaults.roleplay_prompt,
                "memory_prompt": defaults.memory_prompt,
                "dialogue_author_prompt": defaults.dialogue_author_prompt,
                "diffuser_prompt": defaults.diffuser_prompt,
                "sparkle_assistant_prompt": defaults.sparkle_assistant_prompt,
                "vision_persona_prompt": defaults.vision_persona_prompt,
            },
            "prompt_variants": prompt_variants,
            "default_prompt_variants": default_prompt_variants,
            "is_cloud_llm": is_cloud_llm,
            "i18n": trans_repo.get_entity_translations_map("system_prompt", 1),
        }
    )


@api_admin_config_bp.route("/prompts", methods=["PUT"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def update_prompts_config():
    data = parse_request_payload()
    settings_repo = SettingsRepository()
    settings = settings_repo.get_settings()
    prompts = data.get("prompts") if isinstance(data.get("prompts"), dict) else data
    try:
        SettingsService().update_prompts(
            settings,
            roleplay_prompt=str(prompts.get("roleplay_prompt", settings.prompts.roleplay_prompt)),
            memory_prompt=str(prompts.get("memory_prompt", settings.prompts.memory_prompt)),
            dialogue_author_prompt=str(prompts.get("dialogue_author_prompt", settings.prompts.dialogue_author_prompt)),
            diffuser_prompt=str(prompts.get("diffuser_prompt", settings.prompts.diffuser_prompt)),
            vision_persona_prompt=str(prompts.get("vision_persona_prompt", settings.prompts.vision_persona_prompt)),
        )
        settings_repo.save_settings(settings)
        trigger_translation_sync(manual=False)
        return jsonify({"saved": True})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400
