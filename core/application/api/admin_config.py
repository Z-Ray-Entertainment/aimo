from __future__ import annotations

from flask import Blueprint, jsonify

from application.api.auth import require_permission
from application.api.helpers import parse_request_payload
from domain.permissions.models import FunctionPermission
from domain.settings.services import SettingsService
from infrastructure.provider_registry import ProviderRegistry
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.translation.worker import trigger_translation_sync
from shared.exceptions import AimoError

api_admin_config_bp = Blueprint("api_admin_config", __name__, url_prefix="/api/admin")


@api_admin_config_bp.route("/services", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_services_config():
    settings = SettingsRepository().get_settings()
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
                "utility_model": settings.tasks.utility_model,
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
    settings = SettingsRepository().get_settings()
    trans_repo = TranslationRepository()
    return jsonify(
        {
            "prompts": {
                "roleplay_prompt": settings.prompts.roleplay_prompt,
                "memory_prompt": settings.prompts.memory_prompt,
                "dialogue_author_prompt": settings.prompts.dialogue_author_prompt,
                "diffuser_prompt": settings.prompts.diffuser_prompt,
                "vision_persona_prompt": settings.prompts.vision_persona_prompt,
            },
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
