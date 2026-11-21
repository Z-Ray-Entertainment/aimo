from __future__ import annotations

from flask import jsonify

from application.api.auth import get_current_user, is_admin, require_permission
from application.api.chat import api_chat_bp
from application.api.chat.shared import _get_authorized_session
from application.api.helpers import parse_request_payload
from domain.chat.services import ChatService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from shared.exceptions import AimoError


@api_chat_bp.route("/sessions", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def list_chat_sessions():
    user = get_current_user()
    sessions = ChatRepository().list_all_sessions_for_user(user.id)
    return jsonify(
        {
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "character_id": s.character_id,
                    "persona_id": s.persona_id,
                    "active_worldinfo_id": s.active_worldinfo_id,
                    "current_location_id": s.current_location_id,
                    "last_message_at": s.last_message_at.isoformat(),
                }
                for s in sessions
            ]
        }
    )


@api_chat_bp.route("/sessions", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def create_chat_session():
    user = get_current_user()
    data = parse_request_payload()
    try:
        character_id = int(data.get("character_id", 0))
        persona_id = int(data.get("persona_id", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid character_id or persona_id."}), 400

    char = CharacterRepository().get_by_id(character_id)
    if char is None or not char.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Character not found."}), 404

    persona = PersonaRepository().get_by_id(persona_id)
    if persona is None or not persona.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Persona not found."}), 404

    raw_wi = data.get("worldinfo_id")
    worldinfo_id = int(raw_wi) if raw_wi not in (None, "", 0, "0") else None
    if worldinfo_id is not None:
        wi = WorldInfoRepository().get_by_id(worldinfo_id)
        if wi is None or not wi.is_visible_to_user(user.id, is_admin()):
            return jsonify({"error": "WorldInfo not found."}), 404

    try:
        session_obj = ChatService().create_session(
            user_id=user.id,
            character=char,
            persona=persona,
            active_worldinfo_id=worldinfo_id,
            title=str(data.get("title") or "").strip() or None,
        )
        saved = ChatRepository().create_session(session_obj)
        return jsonify({"id": saved.id, "title": saved.title}), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_chat_bp.route("/<int:session_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def get_chat_session(session_id: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    messages = ChatRepository().get_messages(session_id, limit=None)
    user_lang = (user.language or "en")[:2].lower()
    tier = RelationshipRepository().get_tier(chat_session.relationship_value, language=user_lang)
    return jsonify(
        {
            "session": {
                "id": chat_session.id,
                "title": chat_session.title,
                "character_id": chat_session.character_id,
                "persona_id": chat_session.persona_id,
                "persona_locked": chat_session.persona_locked,
                "active_worldinfo_id": chat_session.active_worldinfo_id,
                "current_location_id": chat_session.current_location_id,
                "events_enabled": chat_session.events_enabled,
                "thinking_enabled": chat_session.thinking_enabled,
                "cooldown_counter": chat_session.cooldown_counter,
                "relationship_tier_name": tier.name,
            },
            "messages": [
                {
                    "id": m.id,
                    "message_idx": m.message_idx,
                    "role": m.role.value,
                    "system_type": m.system_type,
                    "content": m.content,
                    "english_content": m.content,
                    "localized_content": m.content,
                    "image_path": m.image_path,
                    "emotion_tag": m.emotion_tag,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }
    )


@api_chat_bp.route("/<int:session_id>", methods=["PUT"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def update_chat_session(session_id: int):
    user = get_current_user()
    chat_session, admin_flag = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = parse_request_payload()
    chat_service = ChatService()
    try:
        if "persona_id" in data:
            new_persona_id = int(data["persona_id"])
            persona = PersonaRepository().get_by_id(new_persona_id)
            if persona is None or not persona.is_visible_to_user(user.id, admin_flag):
                return jsonify({"error": "Persona not found."}), 404
            chat_service.change_persona(chat_session, new_persona_id)

        if "active_worldinfo_id" in data:
            raw_wi = data["active_worldinfo_id"]
            new_wi_id = int(raw_wi) if raw_wi not in (None, "", 0, "0") else None
            if new_wi_id is not None:
                wi = WorldInfoRepository().get_by_id(new_wi_id)
                if wi is None or not wi.is_visible_to_user(user.id, admin_flag):
                    return jsonify({"error": "WorldInfo not found."}), 404
            chat_service.switch_worldinfo(chat_session, new_wi_id)

        if "events_enabled" in data:
            chat_session.events_enabled = bool(data["events_enabled"])
        if "thinking_enabled" in data:
            chat_session.thinking_enabled = bool(data["thinking_enabled"])
        if data.get("reset_relationship"):
            chat_service.reset_relationship(chat_session)

        saved = ChatRepository().update_session(chat_session)
        return jsonify({"id": saved.id, "updated": True})
    except (AimoError, ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_chat_bp.route("/<int:session_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_chat_session(session_id: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404
    deleted = ChatRepository().delete_session(session_id)
    return jsonify({"deleted": deleted})


@api_chat_bp.route("/<int:session_id>/memories/<int:memory_id>", methods=["PUT"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def update_chat_memory(session_id: int, memory_id: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404
    mem_repo = MemoryRepository()
    mem = mem_repo.get_by_id(memory_id)
    if mem is None or mem.chat_session_id != session_id:
        return jsonify({"error": "Memory not found."}), 404
    data = parse_request_payload()
    from domain.memories.services import MemoryService
    try:
        updated = MemoryService().update_memory(
            mem,
            title=str(data.get("title", mem.title)),
            tags=data.get("tags", mem.tags),
            summary=str(data.get("summary", mem.summary)),
        )
        saved = mem_repo.update_memory(updated)
        return jsonify({"id": saved.id, "title": saved.title, "tags": saved.tags, "summary": saved.summary})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_chat_bp.route("/<int:session_id>/memories/<int:memory_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_chat_memory(session_id: int, memory_id: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404
    mem_repo = MemoryRepository()
    mem = mem_repo.get_by_id(memory_id)
    if mem is None or mem.chat_session_id != session_id:
        return jsonify({"error": "Memory not found."}), 404
    return jsonify({"deleted": mem_repo.delete_memory(memory_id)})
