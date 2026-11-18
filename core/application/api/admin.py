import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.auth import require_permission
from domain.permissions.models import FunctionPermission
from domain.settings.models import (
    RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
    ImageGenBackend,
    LLMBackend,
    get_recommended_models_for_backend,
    get_recommended_task_models,
)
from domain.settings.services import SettingsService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider, probe_llm_backend
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

api_admin_bp = Blueprint("api_admin", __name__, url_prefix="/api/admin")


@api_admin_bp.route("/models", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def list_models():
    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    try:
        if isinstance(llm, GoogleAILLMProvider):
            models, image_models = llm.list_model_catalog()
        else:
            models = llm.list_models()
            image_models = []
        return jsonify(
            {
                "backend": settings.llm_backend.value,
                "models": models,
                "image_models": image_models,
                "healthy": True,
            }
        )
    except AimoError as exc:
        return jsonify(
            {
                "backend": settings.llm_backend.value,
                "models": [],
                "image_models": [],
                "healthy": False,
                "error": str(exc),
            }
        )


@api_admin_bp.route("/models/recommended", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_recommended_models():
    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    installed: list[str] = []
    image_models: list[str] = []
    healthy = False
    try:
        if isinstance(llm, GoogleAILLMProvider):
            installed, image_models = llm.list_model_catalog()
        else:
            installed = llm.list_models()
        healthy = True
    except AimoError:
        installed = []

    rec_by_role = get_recommended_task_models(settings.llm_backend)
    roles_detail = get_recommended_models_for_backend(settings.llm_backend)
    unique_models = list(
        dict.fromkeys(
            [
                rec_by_role["roleplay"],
                rec_by_role["memory"],
                rec_by_role["assistant"],
                rec_by_role["vision"],
                rec_by_role["classification"],
            ]
        )
    )
    model_statuses = {m: (m in installed) for m in unique_models}

    return jsonify(
        {
            "backend": settings.llm_backend.value,
            "recommended_by_role": rec_by_role,
            "roles_detail": roles_detail,
            "unique_models": unique_models,
            "model_statuses": model_statuses,
            "image_models": image_models,
            "recommended_image_model": (
                RECOMMENDED_GOOGLE_AI_IMAGE_MODEL
                if settings.llm_backend == LLMBackend.GOOGLE_AI
                else None
            ),
            "llm_healthy": healthy,
            "ollama_healthy": healthy if settings.llm_backend == LLMBackend.OLLAMA else False,
        }
    )


@api_admin_bp.route("/models/apply-recommended", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def apply_recommended_models_endpoint():
    settings_repo = SettingsRepository()
    settings = settings_repo.get_settings()
    settings = SettingsService().apply_recommended_task_models(settings)
    settings_repo.save_settings(settings)
    return jsonify(
        {
            "status": "success",
            "backend": settings.llm_backend.value,
            "tasks": {
                "roleplay_model": settings.tasks.roleplay_model,
                "memory_model": settings.tasks.memory_model,
                "assistant_model": settings.tasks.assistant_model,
                "vision_model": settings.tasks.vision_model,
                "classification_model": settings.tasks.classification_model,
            },
            "google_ai_image_model": settings.google_ai_image_model,
        }
    )


@api_admin_bp.route("/llm/verify", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def verify_llm_connection():
    data = request.get_json(silent=True) or request.form.to_dict()
    settings = SettingsRepository().get_settings()
    raw_backend = str(data.get("llm_backend") or settings.llm_backend.value).strip()
    ollama_url = str(data.get("ollama_url") or settings.ollama_url).strip()
    raw_api_key = str(data.get("google_ai_api_key") or "").strip()
    effective_key = raw_api_key or settings.google_ai_api_key

    result = probe_llm_backend(
        backend=raw_backend,
        ollama_url=ollama_url,
        google_ai_api_key=effective_key,
    )
    return jsonify(result)


@api_admin_bp.route("/models/pull", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def pull_model():
    settings = SettingsRepository().get_settings()
    if settings.llm_backend != LLMBackend.OLLAMA:
        return (
            jsonify(
                {
                    "error": "Model pull is only supported when Ollama is the active backend."
                }
            ),
            400,
        )

    data = request.get_json(silent=True) or request.form.to_dict()
    model_name = str(data.get("name", "")).strip()
    if not model_name:
        return jsonify({"error": "Model name is required."}), 400

    llm = get_llm_provider(settings)

    def generate():
        try:
            for chunk in llm.pull_model(model_name):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'status': 'success', 'completed': True})}\n\n"
        except AimoError as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@api_admin_bp.route("/models/<path:model_name>", methods=["DELETE"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def delete_model(model_name: str):
    settings = SettingsRepository().get_settings()
    if settings.llm_backend != LLMBackend.OLLAMA:
        return (
            jsonify(
                {
                    "error": "Model deletion is only supported when Ollama is the active backend."
                }
            ),
            400,
        )

    llm = get_llm_provider(settings)
    try:
        deleted = llm.delete_model(model_name)
        return jsonify({"deleted": deleted, "model": model_name})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_admin_bp.route("/health", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def check_services_health():
    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    img_gen = get_image_gen_provider(settings)
    llm_ok = llm.check_health()
    img_ok = img_gen.check_health()
    return jsonify(
        {
            "backend": settings.llm_backend.value,
            "llm": llm_ok,
            "ollama": llm_ok if settings.llm_backend == LLMBackend.OLLAMA else False,
            "google_ai": llm_ok if settings.llm_backend == LLMBackend.GOOGLE_AI else False,
            "image_gen_backend": settings.image_gen_backend.value,
            "image_gen": img_ok,
            "comfyui": img_ok if settings.image_gen_backend == ImageGenBackend.COMFYUI else False,
        }
    )


@api_admin_bp.route("/backdrop", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_backdrop():
    settings = SettingsRepository().get_settings()
    return jsonify(
        {
            "default_backdrop_path": settings.default_backdrop_path,
            "has_backdrop": bool(settings.default_backdrop_path),
        }
    )


@api_admin_bp.route("/backdrop", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def update_backdrop():
    settings_repo = SettingsRepository()
    settings_service = SettingsService()
    settings = settings_repo.get_settings()
    storage = FileStorage()

    file_obj = request.files.get("backdrop")
    if file_obj and file_obj.filename:
        try:
            rel_path = storage.save_background(file_obj.stream, file_obj.filename)
            settings = settings_service.update_default_backdrop(settings, rel_path)
            settings_repo.save_settings(settings)
            return jsonify(
                {
                    "success": True,
                    "default_backdrop_path": settings.default_backdrop_path,
                }
            )
        except AimoError as exc:
            return jsonify({"error": str(exc)}), 400

    data = request.get_json(silent=True) or request.form.to_dict()
    if data.get("clear"):
        settings = settings_service.update_default_backdrop(settings, None)
        settings_repo.save_settings(settings)
        return jsonify(
            {
                "success": True,
                "default_backdrop_path": None,
            }
        )

    if "backdrop_path" in data:
        new_path = data.get("backdrop_path")
        settings = settings_service.update_default_backdrop(settings, new_path)
        settings_repo.save_settings(settings)
        return jsonify(
            {
                "success": True,
                "default_backdrop_path": settings.default_backdrop_path,
            }
        )

    return jsonify({"error": "No backdrop file or path provided."}), 400
