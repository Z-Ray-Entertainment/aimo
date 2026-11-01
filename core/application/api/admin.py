import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.auth import require_permission
from domain.permissions.models import FunctionPermission
from domain.settings.services import SettingsService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider
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
        models = llm.list_models()
        return jsonify({"models": models, "healthy": True})
    except AimoError as exc:
        return jsonify({"models": [], "healthy": False, "error": str(exc)})


@api_admin_bp.route("/models/pull", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def pull_model():
    data = request.get_json(silent=True) or request.form.to_dict()
    model_name = str(data.get("name", "")).strip()
    if not model_name:
        return jsonify({"error": "Model name is required."}), 400

    settings = SettingsRepository().get_settings()
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
    return jsonify(
        {
            "ollama": llm.check_health(),
            "comfyui": img_gen.check_health(),
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
