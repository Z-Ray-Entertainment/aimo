from __future__ import annotations

from flask import Blueprint, abort, send_from_directory

from application.api.auth import get_current_user
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.storage.file_storage import FileStorage
from shared.config import Config
from shared.exceptions import InfrastructureError

api_uploads_bp = Blueprint("api_uploads", __name__, url_prefix="/api/uploads")


@api_uploads_bp.route("/<path:filename>", methods=["GET"])
def get_uploaded_file(filename: str):
    user = get_current_user()
    if user is None:
        settings = SettingsRepository().get_settings()
        default_bg = (settings.default_backdrop_path or "").strip() if settings else ""
        if not default_bg or filename != default_bg:
            abort(401)
    storage = FileStorage(Config.UPLOAD_DIR)
    try:
        resolved = storage.resolve_path(filename)
    except InfrastructureError:
        abort(404)
    if not resolved.is_file():
        abort(404)
    rel = resolved.relative_to(storage.base_upload_dir)
    return send_from_directory(str(storage.base_upload_dir), str(rel), max_age=86400)
