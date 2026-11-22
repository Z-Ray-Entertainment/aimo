from __future__ import annotations

from flask import Blueprint, jsonify

from application.api.auth import require_auth
from application.api.helpers import parse_request_payload, require_current_user
from domain.auth.services import AuthService
from domain.translation.models import Language
from infrastructure.repositories.user_repository import UserRepository
from shared.exceptions import AimoError

api_settings_bp = Blueprint("api_settings", __name__, url_prefix="/api/settings")


@api_settings_bp.route("/profile", methods=["GET"])
@require_auth
def get_profile():
    user = require_current_user()
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "language": user.language or "en",
            "creator_tag": user.creator_tag,
            "ember_particles_enabled": bool(user.ember_particles_enabled),
        }
    )


@api_settings_bp.route("/profile", methods=["PUT"])
@require_auth
def update_profile():
    user = require_current_user()
    data = parse_request_payload()
    user_repo = UserRepository()
    auth_service = AuthService()

    try:
        if "language" in data:
            user.language = Language.resolve(str(data["language"])).value
        if "ember_particles_enabled" in data:
            user.ember_particles_enabled = bool(data["ember_particles_enabled"])
        if "username" in data and str(data["username"]).strip():
            user.username = str(data["username"]).strip()
        if "new_password" in data and str(data["new_password"]):
            current_pw = str(data.get("current_password") or "")
            if not auth_service.verify_password(current_pw, user.password_hash):
                return jsonify({"error": "Current password is incorrect."}), 400
            user.password_hash = auth_service.hash_password(str(data["new_password"]))

        saved = user_repo.update_user(user)
        return jsonify(
            {
                "id": saved.id,
                "username": saved.username,
                "email": saved.email,
                "language": saved.language,
                "ember_particles_enabled": bool(saved.ember_particles_enabled),
            }
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400
