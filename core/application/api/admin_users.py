from __future__ import annotations

from flask import Blueprint, jsonify

from application.api.auth import require_permission
from application.api.helpers import parse_request_payload
from domain.auth.services import AuthService
from domain.permissions.models import FunctionPermission, Preset, UserPermissions
from domain.permissions.services import PermissionService
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.user_repository import UserRepository
from shared.exceptions import AimoError

api_admin_users_bp = Blueprint("api_admin_users", __name__, url_prefix="/api/admin/users")


def _serialize_user(user, perms) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "language": user.language or "en",
        "creator_tag": user.creator_tag,
        "is_initial_admin": user.is_initial_admin,
        "permissions": sorted(perms.permissions) if perms else [],
    }


@api_admin_users_bp.route("", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def list_users():
    user_repo = UserRepository()
    users = user_repo.list_all()
    return jsonify(
        {
            "users": [
                _serialize_user(u, user_repo.get_permissions(u.id) if u.id else None)
                for u in users
            ]
        }
    )


@api_admin_users_bp.route("", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def create_user():
    data = parse_request_payload()
    user_repo = UserRepository()
    auth_service = AuthService()
    perm_service = PermissionService()
    try:
        user = auth_service.create_user(
            username=str(data.get("username") or "").strip(),
            email=str(data.get("email") or "").strip(),
            password=str(data.get("password") or ""),
        )
        raw_lang = str(data.get("language") or "").strip()
        if raw_lang:
            auth_service.assign_language(user, raw_lang)
        if user_repo.get_by_email(user.email) is not None:
            return jsonify({"error": "Email already exists."}), 409

        saved = user_repo.create(user)
        perms = UserPermissions(user_id=saved.id, permissions=set())
        raw_perms = data.get("permissions")
        if isinstance(raw_perms, list):
            for flag in raw_perms:
                perm_service.grant_permission(saved, perms, str(flag))
        else:
            preset = Preset.resolve(str(data.get("preset") or Preset.USER.value))
            perm_service.assign_preset(saved, perms, preset)
        user_repo.save_permissions(perms)

        PersonaRepository().create(
            PersonaService().create_persona(
                user_id=saved.id,
                name=saved.username,
                gender=Gender.NON_BINARY,
                portrait_path="portraits/default.png",
                description="",
                is_default=True,
            )
        )
        return jsonify(_serialize_user(saved, user_repo.get_permissions(saved.id))), 201
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_admin_users_bp.route("/<int:user_id>", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_user(user_id: int):
    user_repo = UserRepository()
    target = user_repo.get_by_id(user_id)
    if target is None:
        return jsonify({"error": "User not found."}), 404
    return jsonify(_serialize_user(target, user_repo.get_permissions(user_id)))


@api_admin_users_bp.route("/<int:user_id>", methods=["PUT"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def update_user(user_id: int):
    user_repo = UserRepository()
    target = user_repo.get_by_id(user_id)
    if target is None:
        return jsonify({"error": "User not found."}), 404

    data = parse_request_payload()
    auth_service = AuthService()
    perm_service = PermissionService()
    try:
        if "username" in data and str(data["username"]).strip():
            auth_service.update_name(target, str(data["username"]).strip())
        if "email" in data and str(data["email"]).strip():
            auth_service.update_email(target, str(data["email"]).strip().lower())
        if "language" in data:
            auth_service.assign_language(target, str(data["language"]).strip())
        if "password" in data and str(data["password"]):
            auth_service.change_password(target, str(data["password"]))

        saved = user_repo.update(target)
        if "preset" in data and data["preset"]:
            current_perms = user_repo.get_permissions(user_id)
            perm_service.assign_preset(saved, current_perms, str(data["preset"]))
            user_repo.save_permissions(current_perms)
        elif "permissions" in data and isinstance(data["permissions"], list):
            current_perms = user_repo.get_permissions(user_id)
            desired = {FunctionPermission.resolve(str(p)).value for p in data["permissions"]}
            for existing_flag in list(current_perms.permissions):
                if existing_flag not in desired:
                    perm_service.revoke_permission(saved, current_perms, existing_flag)
            for new_flag in desired:
                perm_service.grant_permission(saved, current_perms, new_flag)
            user_repo.save_permissions(current_perms)

        return jsonify(_serialize_user(saved, user_repo.get_permissions(user_id)))
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_admin_users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def delete_user(user_id: int):
    user_repo = UserRepository()
    target = user_repo.get_by_id(user_id)
    if target is None:
        return jsonify({"error": "User not found."}), 404
    try:
        PermissionService().assert_modifiable_user(target)
        user_repo.delete(user_id)
        return jsonify({"deleted": True})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 403
