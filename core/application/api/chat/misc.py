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

@api_chat_bp.route("/notifications", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def poll_chat_notifications():
    user = get_current_user()
    assert user is not None and user.id is not None

    raw_active = request.args.get("active_session_id", "").strip()
    active_session_id = int(raw_active) if raw_active.isdigit() else None

    to_deliver: list[dict] = []
    with _TASKS_LOCK:
        notifs = _USER_NOTIFICATIONS.get(user.id, [])
        remaining: list[dict] = []
        for item in notifs:
            if active_session_id is not None and item["session_id"] == active_session_id:
                continue
            to_deliver.append(item)
        _USER_NOTIFICATIONS[user.id] = remaining

    return jsonify({"notifications": to_deliver})


@api_chat_bp.route("/notifications/<string:notification_id>/ack", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def ack_chat_notification(notification_id: str):
    user = get_current_user()
    assert user is not None and user.id is not None

    with _TASKS_LOCK:
        notifs = _USER_NOTIFICATIONS.get(user.id, [])
        _USER_NOTIFICATIONS[user.id] = [
            item for item in notifs if item.get("id") != notification_id
        ]

    return jsonify({"status": "acknowledged"})


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>/translate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def translate_chat_message(session_id: int, message_idx: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    target_lang = str(data.get("target_language") or data.get("language") or "de").strip().lower()

    chat_repo = ChatRepository()
    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()
    trans_service = TranslationService()

    msg = chat_repo.get_message_by_idx(session_id, message_idx)
    if msg is None:
        return jsonify({"error": "Message not found."}), 404

    source_text = msg.content.strip()
    if not source_text:
        return jsonify({"error": "Message has no translatable text."}), 400

    source_hash = trans_service.compute_source_hash(source_text)
    cached_rec = trans_repo.get_translation(source_hash, target_lang)
    if cached_rec:
        translated = cached_rec.translated_text
    else:
        settings = settings_repo.get_settings()
        llm = get_llm_provider(settings)
        translated = trans_service.translate_text(
            text=source_text,
            target_language=target_lang,
            llm_provider=llm,
            model=settings.tasks.assistant_model,
        )
        if translated:
            rec = trans_service.create_record(
                english_text=source_text,
                target_language=target_lang,
                translated_text=translated,
            )
            trans_repo.save_translation(rec)

    msg.content = translated
    chat_repo.update_message(msg)

    return jsonify(
        {
            "message_idx": msg.message_idx,
            "translated_text": translated,
            "original_text": source_text,
            "target_language": target_lang,
        }
    )


@api_chat_bp.route("/translate-text", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def translate_arbitrary_text():
    data = request.get_json(silent=True) or request.form.to_dict()
    source_text = str(data.get("text", "")).strip()
    target_lang = str(data.get("target_language", "de")).strip().lower()

    if not source_text:
        return jsonify({"error": "Text is required."}), 400

    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()
    trans_service = TranslationService()

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)
    translated = trans_service.translate_text(
        text=source_text,
        target_language=target_lang,
        llm_provider=llm,
        model=settings.tasks.assistant_model,
    )

    if translated:
        rec = trans_service.create_record(
            english_text=source_text,
            target_language=target_lang,
            translated_text=translated,
        )
        trans_repo.save_translation(rec)

    return jsonify(
        {
            "translated_text": translated,
            "target_language": target_lang,
        }
    )


@api_chat_bp.route("/<int:session_id>/thinking", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def toggle_session_thinking(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    raw_val = data.get("thinking_enabled")
    if raw_val is None:
        raw_val = request.form.get("thinking_enabled")

    if raw_val is None:
        chat_session.thinking_enabled = not chat_session.thinking_enabled
    else:
        chat_session.thinking_enabled = bool(raw_val and str(raw_val).lower() not in ("0", "false", "off"))

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "thinking_enabled": chat_session.thinking_enabled,
    })

