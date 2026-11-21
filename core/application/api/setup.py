from __future__ import annotations

import json
from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.helpers import parse_request_payload
from domain.auth.services import AuthService
from domain.permissions.models import Preset
from domain.permissions.services import PermissionService
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from domain.settings.services import SettingsService
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.llm.factory import LLM_PROVIDER_CLASSES, get_llm_provider_class
from infrastructure.provider_registry import ProviderRegistry
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.user_repository import UserRepository
from shared.exceptions import AimoError

api_setup_bp = Blueprint("api_setup", __name__, url_prefix="/api/setup")


@api_setup_bp.route("/status", methods=["GET"])
def setup_status():
    total_users = UserRepository().count_users()
    settings = SettingsRepository().get_settings()
    llm_providers = [
        {
            "id": cls.PROVIDER_ID,
            "display_name": cls.DISPLAY_NAME,
            "badge": cls.BADGE_LABEL,
            "is_cloud": cls.is_cloud_provider(),
            "description": cls.DESCRIPTION,
            "default_config": cls.get_default_config(),
            "recommended_tasks": cls.get_recommended_task_models(),
            "recommended_models": cls.get_recommended_models(),
            "unique_recommended_models": cls.get_unique_recommended_models(),
        }
        for cls in LLM_PROVIDER_CLASSES.values()
    ]
    return jsonify(
        {
            "first_boot_required": total_users == 0,
            "llm_backend": settings.llm_backend,
            "image_gen_backend": settings.image_gen_backend,
            "search_backend": settings.search_backend,
            "recommended_google_image_model": GoogleAIImageGenProvider.get_recommended_model() or "",
            "llm_providers": llm_providers,
        }
    )


@api_setup_bp.route("/verify-backend", methods=["POST"])
def verify_setup_backend():
    if UserRepository().count_users() > 0:
        return jsonify({"error": "Setup already completed."}), 403
    data = parse_request_payload()
    backend = str(data.get("llm_backend") or "ollama").strip().lower()
    cfg = data.get("config") if isinstance(data.get("config"), dict) else {}
    try:
        llm_cls = get_llm_provider_class(backend)
        validated = llm_cls.validate_active_config(cfg, llm_cls.get_default_config())
        provider = llm_cls(**validated)
        healthy = provider.check_health()
        models = provider.list_models() if healthy else []
        return jsonify({"healthy": healthy, "models": models, "backend": llm_cls.PROVIDER_ID})
    except AimoError as exc:
        return jsonify({"error": str(exc), "healthy": False}), 400


@api_setup_bp.route("/models/pull", methods=["POST"])
def pull_setup_ollama_model():
    if UserRepository().count_users() > 0:
        return jsonify({"error": "Setup already completed."}), 403
    data = parse_request_payload()
    model_name = str(data.get("name") or "").strip()
    if not model_name:
        return jsonify({"error": "Model name is required."}), 400
    raw_url = str(data.get("ollama_url") or data.get("base_url") or "").strip()
    llm_cls = get_llm_provider_class("ollama")
    validated = llm_cls.validate_active_config(
        {"base_url": raw_url} if raw_url else {},
        llm_cls.get_default_config(),
    )
    llm = llm_cls(**validated)

    def generate():
        try:
            for chunk in llm.pull_model(model_name):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'status': 'success', 'completed': True})}\n\n"
        except AimoError as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream; charset=utf-8",
    )


@api_setup_bp.route("/first-boot", methods=["POST"])
def complete_first_boot():
    user_repo = UserRepository()
    if user_repo.count_users() > 0:
        return jsonify({"error": "Setup already completed."}), 403

    data = parse_request_payload()
    try:
        auth_service = AuthService()
        perm_service = PermissionService()
        persona_service = PersonaService()
        settings_repo = SettingsRepository()
        settings = settings_repo.get_settings()

        username = str(data.get("username") or "").strip()
        email = str(data.get("email") or "").strip()
        password = str(data.get("password") or "")
        language = str(data.get("language") or "en").strip().lower()[:2] or "en"

        user = auth_service.create_user(
            username=username,
            email=email,
            password=password,
            is_initial_admin=True,
            language=language,
        )
        perms = perm_service.create_for_preset(0, Preset.ADMIN)
        saved_user = user_repo.create_user(user, perms)

        persona = persona_service.create_persona(
            user_id=saved_user.id,
            name=str(data.get("persona_name") or username).strip(),
            gender=Gender.resolve(str(data.get("persona_gender") or Gender.NON_BINARY.value)),
            portrait_path="portraits/default.png",
            description=str(data.get("persona_description") or "").strip(),
            appearance=str(data.get("persona_appearance") or "").strip(),
            is_default=True,
        )
        PersonaRepository().create(persona)

        llm_backend = str(data.get("llm_backend") or settings.llm_backend).strip().lower()
        llm_configs = data.get("llm_configs") if isinstance(data.get("llm_configs"), dict) else {}
        image_gen_backend = str(data.get("image_gen_backend") or settings.image_gen_backend).strip().lower()
        image_gen_configs = data.get("image_gen_configs") if isinstance(data.get("image_gen_configs"), dict) else {}
        search_backend = str(data.get("search_backend") or settings.search_backend).strip().lower()
        search_configs = data.get("search_configs") if isinstance(data.get("search_configs"), dict) else {}

        ProviderRegistry.update_backend_configuration(
            settings,
            llm_backend=llm_backend,
            llm_configs=llm_configs,
            image_gen_backend=image_gen_backend,
            image_gen_configs=image_gen_configs,
            search_backend=search_backend,
            search_configs=search_configs,
        )
        if data.get("apply_recommended_models", True):
            ProviderRegistry.apply_recommended_models(settings)
        else:
            SettingsService().apply_task_model_map(
                settings,
                {
                    "roleplay_model": str(data.get("roleplay_model") or settings.tasks.roleplay_model),
                    "memory_model": str(data.get("memory_model") or settings.tasks.memory_model),
                    "utility_model": str(data.get("utility_model") or settings.tasks.utility_model),
                    "vision_model": str(data.get("vision_model") or settings.tasks.vision_model),
                    "classification_model": str(data.get("classification_model") or settings.tasks.classification_model),
                },
            )
        settings_repo.save_settings(settings)

        return jsonify({"status": "initialized", "user_id": saved_user.id, "username": saved_user.username}), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400
