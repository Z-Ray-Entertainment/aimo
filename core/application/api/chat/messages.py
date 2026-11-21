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

from application.chat_services.turn_orchestrator import start_background_turn as _start_background_turn

def _revert_relationship_for_messages(
    chat_service: ChatService,
    chat_session: ChatSession,
    messages: list[Message],
) -> bool:
    reverted = False
    for msg in messages:
        if msg.role != MessageRole.CHARACTER:
            continue
        raw_delta = msg.metadata.get("relationship_delta") if msg.metadata else None
        if isinstance(raw_delta, (int, float)) and not isinstance(raw_delta, bool):
            chat_service.revert_relationship_delta(chat_session, float(raw_delta))
            reverted = True
    return reverted


@api_chat_bp.route("/<int:session_id>/regenerate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def regenerate_turn(session_id: int):
    user = get_current_user()
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    user_lang = str(data.get("language", "de")).strip()

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()

    all_messages = chat_repo.get_messages(session_id, limit=None)
    narrative_msgs = [
        m for m in all_messages if m.role in (MessageRole.USER, MessageRole.CHARACTER)
    ]
    if not narrative_msgs:
        return jsonify({"error": "Keine Nachrichten zum Neu-Generieren vorhanden."}), 400

    last_msg = narrative_msgs[-1]
    deleted_msg_idx = None
    target_ai_idx = None

    if last_msg.role == MessageRole.CHARACTER:
        if last_msg.message_idx == 0:
            return jsonify({"error": "Die Begrüßung der KI kann nicht neu generiert werden."}), 400

        if _revert_relationship_for_messages(chat_service, chat_session, [last_msg]):
            chat_repo.update_session(chat_session)

        if last_msg.id is not None:
            chat_repo.delete_single_message(last_msg.id)
        else:
            chat_repo.delete_message_by_idx(session_id, last_msg.message_idx)
        mem_repo.delete_after_idx(session_id, last_msg.message_idx - 1)
        deleted_msg_idx = last_msg.message_idx
        target_ai_idx = last_msg.message_idx

        updated_messages = [m for m in all_messages if m.id != last_msg.id]
        user_msgs = [m for m in updated_messages if m.role == MessageRole.USER]
        if not user_msgs:
            return jsonify({"error": "Keine Spielernachricht zum Neu-Generieren gefunden."}), 400
        target_user_msg = user_msgs[-1]

    elif last_msg.role == MessageRole.USER:
        target_user_msg = last_msg
        target_ai_idx = None
    else:
        return jsonify({"error": "Ungültiger Rollenstatus der letzten Nachricht."}), 400

    try:
        task, _, triggered_event = _start_background_turn(
            session_id=session_id,
            user_text=target_user_msg.localized_content or "",
            user_language=user_lang,
            is_admin=is_admin,
            existing_user_msg=target_user_msg,
            target_ai_idx=target_ai_idx,
        )
        return jsonify({
            "task_id": task.task_id,
            "session_id": session_id,
            "deleted_message_idx": deleted_msg_idx,
            "user_message_idx": target_user_msg.message_idx,
            "triggered_event": triggered_event,
        }), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>/prompt", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_message_prompt(session_id: int, message_idx: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404
    with _TASKS_LOCK:
        prompt = _ADMIN_PROMPT_CACHE.get((session_id, message_idx))
    if prompt is None:
        return jsonify({
            "error": "Prompt not available in memory.",
            "prompt": None,
        }), 404
    return jsonify({
        "session_id": session_id,
        "message_idx": message_idx,
        "prompt": prompt,
    })


@api_chat_bp.route("/<int:session_id>/fork", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def fork_chat_session(session_id: int):
    user = get_current_user()
    orig_session, _ = _get_authorized_session(session_id, user)
    if orig_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        fork_point_idx = int(data.get("fork_point_idx", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid fork_point_idx."}), 400

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()
    mem_service = MemoryService()

    all_messages = chat_repo.get_messages(session_id, limit=None)
    forked_session, filtered_messages = chat_service.fork_session(
        session=orig_session,
        messages=all_messages,
        fork_point_idx=fork_point_idx,
    )
    forked_session.user_id = user.id
    saved_fork = chat_repo.create_session(forked_session)

    for msg in filtered_messages:
        msg.session_id = saved_fork.id
        chat_repo.add_message(msg)

    orig_memories = mem_repo.list_for_session(session_id)
    valid_memories = mem_service.filter_memories_for_fork(orig_memories, fork_point_idx)
    for mem in valid_memories:
        mem.id = None
        mem.chat_session_id = saved_fork.id
        mem_repo.add_memory(mem)

    return jsonify(
        {
            "forked_session_id": saved_fork.id,
            "title": saved_fork.title,
        }
    ), 201


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>", methods=["DELETE"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_messages_from_idx(session_id: int, message_idx: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()
    wi_repo = WorldInfoRepository()

    all_before_delete = chat_repo.get_messages(session_id, limit=None)
    msgs_to_delete = [m for m in all_before_delete if m.message_idx >= message_idx]
    _revert_relationship_for_messages(chat_service, chat_session, msgs_to_delete)

    deleted_msgs = chat_repo.delete_messages_after(
        session_id=session_id,
        message_idx=message_idx,
        inclusive=True,
    )
    deleted_mems = mem_repo.delete_after_idx(
        session_id=session_id,
        message_idx=message_idx - 1,
    )

    remaining_messages = chat_repo.get_messages(session_id, limit=None)
    chat_service.recalculate_current_location_after_deletion(chat_session, remaining_messages)
    chat_service.recalculate_events_after_deletion(chat_session, remaining_messages)
    chat_repo.update_session(chat_session)

    curr_loc = (
        wi_repo.get_location(chat_session.current_location_id)
        if chat_session.current_location_id
        else None
    )
    active_wi = (
        wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if chat_session.active_worldinfo_id
        else None
    )

    return jsonify(
        {
            "deleted_messages": deleted_msgs,
            "deleted_memories": deleted_mems,
            "current_location_id": chat_session.current_location_id,
            "current_location": {
                "id": curr_loc.id,
                "name": curr_loc.name,
                "background_image_path": curr_loc.background_image_path,
            } if curr_loc else None,
            "worldinfo_backdrop_path": active_wi.backdrop_image_path if active_wi else None,
        }
    )


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>", methods=["PUT"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def edit_message(session_id: int, message_idx: int):
    user = get_current_user()
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    new_text = str(data.get("content", "")).strip()
    if not new_text:
        return jsonify({"error": "Message content must not be empty."}), 400

    chat_repo = ChatRepository()
    trans_repo = TranslationRepository()
    trans_service = TranslationService()

    msg = chat_repo.get_message_by_idx(session_id, message_idx)
    if msg is None:
        return jsonify({"error": "Message not found."}), 404

    if msg.content:
        old_hash = trans_service.compute_source_hash(msg.content)
        trans_repo.invalidate(old_hash)

    msg.content = new_text
    chat_repo.update_message(msg)

    return jsonify(
        {
            "message_idx": msg.message_idx,
            "content": msg.content,
            "english_content": msg.content,
            "localized_content": msg.content,
        }
    )
