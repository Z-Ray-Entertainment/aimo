from __future__ import annotations

from flask import Blueprint, jsonify, request

from application.api.auth import get_current_permissions, get_current_user, require_auth
from application.api.helpers import parse_request_payload
from domain.auth.services import AuthService
from domain.permissions.models import Preset
from domain.permissions.services import PermissionService
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from domain.translation.models import LANGUAGE_METADATA
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from shared.exceptions import AimoError
from shared.security import LoginRateLimiter

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")
_LOGIN_LIMITER = LoginRateLimiter()


@api_auth_bp.route("/login", methods=["POST"])
def login():
    data = parse_request_payload()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    client_ip = (request.remote_addr or "unknown").strip()
    rate_key = f"{client_ip}:{email}"

    allowed, retry_after = _LOGIN_LIMITER.is_allowed(rate_key)
    if not allowed:
        return jsonify({"error": "Too many failed login attempts.", "retry_after": retry_after}), 429

    user_repo = UserRepository()
    user = user_repo.get_by_email(email)
    if user is None or not AuthService().verify_password(password, user.password_hash):
        _LOGIN_LIMITER.record_failure(rate_key)
        return jsonify({"error": "Invalid email or password."}), 401

    _LOGIN_LIMITER.reset(rate_key)
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "language": user.language or "en",
            "creator_tag": user.creator_tag,
            "is_initial_admin": user.is_initial_admin,
            "ember_particles_enabled": bool(user.ember_particles_enabled),
        }
    )


@api_auth_bp.route("/register", methods=["POST"])
def register():
    data = parse_request_payload()
    user_repo = UserRepository()
    try:
        user = AuthService().create_user(
            username=str(data.get("username") or "").strip(),
            email=str(data.get("email") or "").strip(),
            password=str(data.get("password") or ""),
            language=str(data.get("language") or "en").strip().lower()[:2] or "en",
        )
        if user_repo.get_by_email(user.email) is not None:
            return jsonify({"error": "Email already registered."}), 409
        perms = PermissionService().create_for_preset(0, Preset.USER)
        saved = user_repo.create_user(user, perms)
        default_persona = PersonaService().create_persona(
            user_id=saved.id,
            name=saved.username,
            gender=Gender.NON_BINARY,
            portrait_path="portraits/default.png",
            description="",
            is_default=True,
        )
        PersonaRepository().create(default_persona)
        return jsonify({"id": saved.id, "username": saved.username, "email": saved.email}), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_auth_bp.route("/me", methods=["GET"])
@require_auth
def get_me():
    user = get_current_user()
    perms = get_current_permissions()
    persona_repo = PersonaRepository()
    trans_repo = TranslationRepository()
    personas = persona_repo.list_for_user(user.id)
    default_persona = next((p for p in personas if p.is_default), personas[0] if personas else None)
    settings = SettingsRepository().get_settings()

    persona_items = []
    for p in personas:
        p_trans = trans_repo.get_entity_translations_map("persona", p.id) if p.id else {}
        persona_items.append(
            {
                "id": p.id,
                "name": p.name,
                "gender": p.gender.value,
                "portrait_path": p.portrait_path,
                "description": p.description,
                "appearance": p.appearance,
                "origin_language": p.origin_language,
                "is_default": p.is_default,
                "in_use": persona_repo.is_used_in_any_session(p.id) if p.id else False,
                "i18n_description": p_trans.get("description", {}),
                "i18n_appearance": p_trans.get("appearance", {}),
            }
        )

    return jsonify(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "language": user.language or "en",
                "creator_tag": user.creator_tag,
                "is_initial_admin": user.is_initial_admin,
                "ember_particles_enabled": bool(user.ember_particles_enabled),
            },
            "permissions": sorted(perms.permissions) if perms else [],
            "default_persona_id": default_persona.id if default_persona else None,
            "personas": persona_items,
            "system_backdrop_path": settings.default_backdrop_path if settings else None,
            "languages": [
                {"code": code, "flag": meta["flag"], "label": meta["label"]}
                for code, meta in LANGUAGE_METADATA.items()
            ],
        }
    )
