import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.auth import require_permission
from domain.permissions.models import FunctionPermission
from infrastructure.image_gen.factory import (
    get_image_gen_provider,
    get_image_gen_provider_class,
)
from infrastructure.llm.factory import (
    get_llm_provider,
    get_llm_provider_class,
    probe_llm_backend,
)
from infrastructure.provider_registry import ProviderRegistry
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
        models, image_models = llm.list_model_catalog()
        return jsonify(
            {
                "backend": settings.llm_backend,
                "models": models,
                "image_models": image_models,
                "healthy": True,
            }
        )
    except AimoError as exc:
        return jsonify(
            {
                "backend": settings.llm_backend,
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
    llm_cls = get_llm_provider_class(settings.llm_backend)
    img_cls = get_image_gen_provider_class(settings.image_gen_backend)

    installed: list[str] = []
    image_models: list[str] = []
    healthy = False
    try:
        installed, image_models = llm.list_model_catalog()
        healthy = True
    except AimoError:
        installed = []

    rec_by_role = llm_cls.get_recommended_task_models()
    roles_detail = llm_cls.get_recommended_models()
    unique_models = llm_cls.get_unique_recommended_models()
    model_statuses = {m: (m in installed) for m in unique_models}

    return jsonify(
        {
            "backend": settings.llm_backend,
            "recommended_by_role": rec_by_role,
            "roles_detail": roles_detail,
            "unique_models": unique_models,
            "model_statuses": model_statuses,
            "image_models": image_models,
            "recommended_image_model": img_cls.get_recommended_model(),
            "llm_healthy": healthy,
            "ollama_healthy": healthy if llm_cls.supports_model_management() else False,
        }
    )


@api_admin_bp.route("/models/apply-recommended", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def apply_recommended_models_endpoint():
    settings_repo = SettingsRepository()
    settings = settings_repo.get_settings()
    settings = ProviderRegistry.apply_recommended_models(settings)
    settings_repo.save_settings(settings)
    return jsonify(
        {
            "status": "success",
            "backend": settings.llm_backend,
            "tasks": {
                "roleplay_model": settings.tasks.roleplay_model,
                "memory_model": settings.tasks.memory_model,
                "assistant_model": settings.tasks.assistant_model,
                "vision_model": settings.tasks.vision_model,
                "classification_model": settings.tasks.classification_model,
            },
            "image_gen_config": settings.get_image_gen_config(),
        }
    )


@api_admin_bp.route("/llm/verify", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def verify_llm_connection():
    data = request.get_json(silent=True) or request.form.to_dict()
    settings = SettingsRepository().get_settings()
    raw_backend = str(data.get("llm_backend") or settings.llm_backend).strip().lower()

    submitted_cfg: dict[str, str] = {}
    if isinstance(data.get("config"), dict):
        submitted_cfg = {str(k): str(v) for k, v in data["config"].items()}
    else:
        if "ollama_url" in data:
            submitted_cfg["base_url"] = str(data.get("ollama_url") or "").strip()
        if "base_url" in data:
            submitted_cfg["base_url"] = str(data.get("base_url") or "").strip()
        if "google_ai_api_key" in data:
            submitted_cfg["api_key"] = str(data.get("google_ai_api_key") or "").strip()
        if "api_key" in data:
            submitted_cfg["api_key"] = str(data.get("api_key") or "").strip()

    result = probe_llm_backend(
        backend=raw_backend,
        submitted_config=submitted_cfg,
        existing_config=settings.get_llm_config(raw_backend),
    )
    return jsonify(result)


@api_admin_bp.route("/models/pull", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def pull_model():
    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    if not type(llm).supports_model_management():
        return (
            jsonify(
                {
                    "error": "Model pull is not supported by the active LLM backend."
                }
            ),
            400,
        )

    data = request.get_json(silent=True) or request.form.to_dict()
    model_name = str(data.get("name", "")).strip()
    if not model_name:
        return jsonify({"error": "Model name is required."}), 400

    def generate():
        try:
            for chunk in llm.pull_model(model_name):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'status': 'success', 'completed': True})}\n\n"
        except AimoError as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream; charset=utf-8")


@api_admin_bp.route("/models/<path:model_name>", methods=["DELETE"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def delete_model(model_name: str):
    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    if not type(llm).supports_model_management():
        return (
            jsonify(
                {
                    "error": "Model deletion is not supported by the active LLM backend."
                }
            ),
            400,
        )

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
            "backend": settings.llm_backend,
            "llm": llm_ok,
            "image_gen_backend": settings.image_gen_backend,
            "image_gen": img_ok,
            "comfyui": img_ok if settings.image_gen_backend == "comfyui" else False,
            "ollama": llm_ok if settings.llm_backend == "ollama" else False,
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
    from domain.settings.services import SettingsService

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


@api_admin_bp.route("/translations/status", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def translation_sync_status():
    from infrastructure.translation.worker import get_translation_worker

    return jsonify(get_translation_worker().get_status())


@api_admin_bp.route("/translations/sync", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def trigger_manual_translation_sync():
    from infrastructure.translation.worker import get_translation_worker

    worker = get_translation_worker()
    worker.trigger_sync(manual=True)
    return jsonify({"status": "started", "worker": worker.get_status()})


@api_admin_bp.route("/translations/cancel", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def cancel_translation_sync():
    from infrastructure.translation.worker import get_translation_worker

    worker = get_translation_worker()
    worker.cancel_sync()
    return jsonify({"status": "cancelling", "worker": worker.get_status()})


@api_admin_bp.route("/translations/notify", methods=["POST"])
def notify_translation_worker():
    from application.api.auth import require_auth as _req_auth
    from infrastructure.llm.factory import get_llm_provider_class
    from infrastructure.repositories.translation_repository import TranslationRepository
    from infrastructure.repositories.user_repository import UserRepository
    from infrastructure.translation.worker import trigger_translation_sync

    settings = SettingsRepository().get_settings()
    is_cloud = get_llm_provider_class(settings.llm_backend).is_cloud_provider()
    if not is_cloud:
        trigger_translation_sync(manual=False)
        return jsonify({"is_cloud": False, "has_missing": False})

    data = request.get_json(silent=True) or {}
    etype = str(data.get("entity_type") or "").strip()
    eid = data.get("entity_id")
    fname = str(data.get("field_name") or "").strip()
    has_missing = False
    if etype and eid and fname:
        target_langs = UserRepository().list_distinct_languages()
        missing = TranslationRepository().get_missing_languages(etype, int(eid), fname, target_langs)
        has_missing = bool(missing)
    return jsonify({"is_cloud": True, "has_missing": has_missing})
