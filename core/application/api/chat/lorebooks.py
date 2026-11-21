from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import threading
import uuid

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.auth import get_current_user, has_perm, require_permission
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.chat.focus_analyzer import PythonFocusAnalyzer, SceneFocus
from domain.chat.models import ChatSession, Message, MessageRole
from domain.chat.prompt_builder import PromptBuilder
from domain.chat.relationship import RelationshipImpact, get_relationship_tier
from domain.chat.services import ChatService
from domain.lorebooks.services import LorebookService
from domain.memories.services import MemoryService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters, get_default_prompt, is_default_prompt
from domain.translation.services import TranslationService
from domain.worldinfo.models import EventCooldownState
from domain.worldinfo.services import WorldInfoService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError
from shared.llm_activity import (
    begin_interactive_llm,
    end_interactive_llm,
    interactive_llm_guard,
    is_interactive_llm_busy,
    touch_interactive_llm,
)
from shared.utils import filter_stopwords, parse_tags, replace_roleplay_placeholders

from application.api.chat import api_chat_bp
from application.api.chat.shared import (
    _ACTIVE_IMAGE_TASKS,
    _ADMIN_PROMPT_CACHE,
    _BACKGROUND_TASKS,
    _TASKS_LOCK,
    _USER_NOTIFICATIONS,
    _BackgroundTurnTask,
    _extract_active_tags,
    _get_authorized_session,
    _record_admin_prompt,
)

logger = logging.getLogger(__name__)

@api_chat_bp.route("/<int:session_id>/lorebooks", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def get_session_lorebooks(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
    lb_repo = LorebookRepository()

    character = char_repo.get_by_id(chat_session.character_id)
    worldinfo = (
        wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if chat_session.active_worldinfo_id
        else None
    )

    char_lb_ids = set(character.linked_lorebook_ids) if character else set()
    wi_lb_id = worldinfo.lorebook_id if (worldinfo and worldinfo.lorebook_id) else None

    # Default lorebook IDs
    default_ids = set(char_lb_ids)
    if wi_lb_id:
        default_ids.add(wi_lb_id)

    # All visible lorebooks for the user
    all_visible = lb_repo.list_visible(user.id)
    all_map = {lb.id: lb for lb in all_visible if lb.id is not None}

    char_conditions = getattr(character, "lorebook_world_conditions", {}) or {}

    def _format_lb(
        lb,
        source: str,
        is_active: bool = True,
        is_locked: bool = False,
        required_worldinfo_id: int | None = None,
        required_worldinfo_name: str | None = None,
    ):
        entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
        all_tags: set[str] = set()
        for e in entries:
            all_tags.update(e.tags)
        return {
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "source": source,
            "is_active": is_active,
            "is_locked": is_locked,
            "required_worldinfo_id": required_worldinfo_id,
            "required_worldinfo_name": required_worldinfo_name,
        }

    default_lorebooks = []
    for lb_id in sorted(default_ids):
        lb = all_map.get(lb_id)
        if lb is None:
            candidate = lb_repo.get_by_id(lb_id)
            if candidate is not None and candidate.is_visible_to_user(user.id, is_admin):
                lb = candidate
        if lb:
            in_char = lb_id in char_lb_ids
            in_wi = lb_id == wi_lb_id
            if in_char and in_wi:
                source = "character & worldinfo"
            elif in_char:
                source = "character"
            else:
                source = "worldinfo"

            is_locked = False
            req_wi_id = None
            req_wi_name = None
            if in_char and lb_id in char_conditions:
                req_wi_id = char_conditions[lb_id]
                req_wi = wi_repo.get_by_id(req_wi_id)
                req_wi_name = req_wi.name if req_wi else f"Welt #{req_wi_id}"
                if chat_session.active_worldinfo_id != req_wi_id:
                    is_locked = True

            if is_locked:
                is_active = False
            else:
                is_active = lb.id not in chat_session.disabled_lorebook_ids

            default_lorebooks.append(
                _format_lb(
                    lb,
                    source,
                    is_active=is_active,
                    is_locked=is_locked,
                    required_worldinfo_id=req_wi_id,
                    required_worldinfo_name=req_wi_name,
                )
            )

    # Alphabetical sort within default lorebooks
    default_lorebooks.sort(key=lambda x: x["name"].lower())

    custom_lorebooks = []
    for lb_id in chat_session.custom_lorebook_ids:
        if lb_id in default_ids:
            continue
        lb = all_map.get(lb_id)
        if lb is None:
            candidate = lb_repo.get_by_id(lb_id)
            if candidate is not None and candidate.is_visible_to_user(user.id, is_admin):
                lb = candidate
        if lb:
            is_active = lb.id not in chat_session.disabled_lorebook_ids
            custom_lorebooks.append(_format_lb(lb, "custom", is_active=is_active))

    # Alphabetical sort within custom lorebooks
    custom_lorebooks.sort(key=lambda x: x["name"].lower())

    active_in_session_ids = default_ids.union(chat_session.custom_lorebook_ids)
    available_lorebooks = []
    for lb in sorted(all_visible, key=lambda x: x.name.lower()):
        entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
        all_tags: set[str] = set()
        for e in entries:
            all_tags.update(e.tags)
        available_lorebooks.append({
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "is_added": lb.id in active_in_session_ids,
        })

    active_count = len([x for x in default_lorebooks if x["is_active"]]) + len(
        [x for x in custom_lorebooks if x["is_active"]]
    )

    return jsonify({
        "session_id": session_id,
        "default_lorebooks": default_lorebooks,
        "custom_lorebooks": custom_lorebooks,
        "available_lorebooks": available_lorebooks,
        "active_count": active_count,
    })


@api_chat_bp.route("/<int:session_id>/lorebooks/toggle", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def toggle_session_lorebook(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    lorebook_id = data.get("lorebook_id")
    if lorebook_id is None:
        lorebook_id = request.form.get("lorebook_id")
    if lorebook_id is None:
        return jsonify({"error": "lorebook_id is required."}), 400

    try:
        lb_id = int(lorebook_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid lorebook_id."}), 400

    lb = LorebookRepository().get_by_id(lb_id)
    if lb is None or not lb.is_visible_to_user(user.id, is_admin):
        return jsonify({"error": "Lorebook not found."}), 404

    active = data.get("active")
    if active is None:
        active = request.form.get("active", "true").lower() in ("true", "1")
    else:
        active = bool(active)

    if active:
        char_repo = CharacterRepository()
        char = char_repo.get_by_id(chat_session.character_id)
        if char and getattr(char, "lorebook_world_conditions", None):
            req_wi_id = char.lorebook_world_conditions.get(lb_id)
            if req_wi_id is not None and req_wi_id != chat_session.active_worldinfo_id:
                return jsonify({
                    "error": "Dieses Lorebook erfordert eine andere Welt und kann in dieser Sitzung nicht aktiviert werden."
                }), 400

    chat_service = ChatService()
    chat_service.toggle_lorebook(chat_session, lb_id, active)

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "lorebook_id": lb_id,
        "is_active": active,
    })


@api_chat_bp.route("/<int:session_id>/lorebooks/custom", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def add_session_custom_lorebook(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    lorebook_id = data.get("lorebook_id")
    if lorebook_id is None:
        lorebook_id = request.form.get("lorebook_id")
    if lorebook_id is None:
        return jsonify({"error": "lorebook_id is required."}), 400

    try:
        lb_id = int(lorebook_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid lorebook_id."}), 400

    lb_repo = LorebookRepository()
    lb = lb_repo.get_by_id(lb_id)
    if lb is None or not lb.is_visible_to_user(user.id, is_admin):
        return jsonify({"error": "Lorebook not found or no access."}), 404

    chat_service = ChatService()
    chat_service.add_custom_lorebook(chat_session, lb_id)

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
    all_tags: set[str] = set()
    for e in entries:
        all_tags.update(e.tags)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "lorebook": {
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "source": "custom",
            "is_active": True,
        },
    }), 201


@api_chat_bp.route("/<int:session_id>/lorebooks/custom/<int:lorebook_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def remove_session_custom_lorebook(session_id: int, lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_service = ChatService()
    chat_service.remove_custom_lorebook(chat_session, lorebook_id)

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "lorebook_id": lorebook_id,
    })
