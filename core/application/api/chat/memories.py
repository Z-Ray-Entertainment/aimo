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
    _PENDING_PROMPTS,
    _TASKS_LOCK,
    _USER_NOTIFICATIONS,
    _BackgroundTurnTask,
    _extract_active_tags,
    _get_authorized_session,
    _record_admin_prompt,
)

logger = logging.getLogger(__name__)

def _run_async_memory_extraction(session_id: int) -> None:
    def _worker() -> None:
        try:
            chat_repo = ChatRepository()
            mem_repo = MemoryRepository()
            settings_repo = SettingsRepository()
            mem_service = MemoryService()

            chat_session = chat_repo.get_session(session_id)
            if chat_session is None:
                return

            all_messages = chat_repo.get_messages(session_id, limit=None)
            narrative_msgs = mem_service.filter_narrative_messages(all_messages)
            existing_memories = mem_repo.list_for_session(session_id)
            last_mem_idx = max((m.message_idx for m in existing_memories), default=0)
            unsummarized = [m for m in narrative_msgs if m.message_idx > last_mem_idx]

            if not mem_service.should_generate_memory(len(unsummarized)):
                return

            chunk = unsummarized[:10]
            target_idx = chunk[-1].message_idx
            settings = settings_repo.get_settings()
            llm = get_llm_provider(settings)

            session_user = UserRepository().get_by_id(chat_session.user_id)
            user_lang = (session_user.language if session_user and session_user.language else "en")[:2].lower()
            raw_mem_prompt = settings.prompts.memory_prompt
            if is_default_prompt("memory_prompt", raw_mem_prompt):
                resolved_mem_prompt = get_default_prompt("memory_prompt", user_lang)
            else:
                resolved_mem_prompt = TranslationRepository().get_localized_field(
                    "system_prompt", 1, "memory_prompt", user_lang, raw_mem_prompt
                )

            msg_dicts = [
                {"role": m.role.value, "content": m.localized_content or m.english_content or ""}
                for m in chunk
            ]
            with interactive_llm_guard():
                title, tags, summary, new_chat_title = mem_service.extract_memory_and_title(
                    last_10_messages=msg_dicts,
                    memory_prompt=resolved_mem_prompt,
                    llm_provider=llm,
                    model=settings.tasks.memory_model,
                    params=settings.params,
                )
            memory = mem_service.create_memory(
                chat_session_id=session_id,
                message_idx=target_idx,
                title=title,
                tags=tags,
                summary=summary,
            )
            mem_repo.add_memory(memory)

            if new_chat_title:
                chat_session.title = new_chat_title
                chat_repo.update_session(chat_session)
        except Exception as exc:
            logger.exception("Background memory generation failed for session %s: %s", session_id, exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()




@api_chat_bp.route("/<int:session_id>/memories", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def list_session_memories(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    mem_repo = MemoryRepository()
    memories = mem_repo.list_for_session(session_id)
    return jsonify(
        {
            "memories": [
                {
                    "id": m.id,
                    "message_idx": m.message_idx,
                    "title": m.title,
                    "tags": m.tags,
                    "summary": m.summary,
                }
                for m in memories
            ]
        }
    )


@api_chat_bp.route("/<int:session_id>/memories/<int:memory_id>/recalculate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def recalculate_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    settings_repo = SettingsRepository()
    mem_service = MemoryService()

    target_memory = mem_repo.get_by_id(memory_id)
    if target_memory is None or target_memory.chat_session_id != session_id:
        return jsonify({"error": "Memory not found."}), 404

    all_messages = chat_repo.get_messages(session_id, limit=None)
    narrative_msgs = mem_service.filter_narrative_messages(all_messages)
    all_memories = mem_repo.list_for_session(session_id)

    chunk = mem_service.extract_messages_for_memory(
        memories=all_memories,
        target_memory=target_memory,
        all_narrative_messages=narrative_msgs,
        chunk_size=10,
    )

    if not chunk:
        return jsonify({"error": "No narrative messages found for this memory episode."}), 400

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)

    msg_dicts = [
        {"role": m.role.value, "content": m.english_content or m.localized_content or ""}
        for m in chunk
    ]

    try:
        title, tags, summary, _ = mem_service.extract_memory_and_title(
            last_10_messages=msg_dicts,
            memory_prompt=settings.prompts.memory_prompt,
            llm_provider=llm,
            model=settings.tasks.memory_model,
            params=settings.params,
        )
    except Exception as exc:
        logger.exception("LLM memory generation failed for session %s, memory %s: %s", session_id, memory_id, exc)
        return jsonify({"error": "LLM memory generation failed."}), 502

    try:
        mem_service.update_memory(
            memory=target_memory,
            title=title,
            tags=tags,
            summary=summary,
        )
        mem_repo.update_memory(target_memory)
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "id": target_memory.id,
            "chat_session_id": target_memory.chat_session_id,
            "message_idx": target_memory.message_idx,
            "title": target_memory.title,
            "tags": target_memory.tags,
            "summary": target_memory.summary,
            "messages_count": len(chunk),
        }
    )


@api_chat_bp.route("/<int:session_id>/memories/<int:memory_id>/translate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def translate_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    mem_repo = MemoryRepository()
    settings_repo = SettingsRepository()
    mem_service = MemoryService()
    trans_service = TranslationService()

    target_memory = mem_repo.get_by_id(memory_id)
    if target_memory is None or target_memory.chat_session_id != session_id:
        return jsonify({"error": "Memory not found."}), 404

    data = request.get_json(silent=True) or {}
    target_lang = str(data.get("target_language") or user.language or "en").strip().lower()[:2]

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)
    model = settings.tasks.assistant_model

    try:
        translated_title = (
            trans_service.translate_text_or_none(
                text=target_memory.title,
                target_language=target_lang,
                llm_provider=llm,
                model=model,
            )
            if target_memory.title
            else None
        )
        translated_summary = (
            trans_service.translate_text_or_none(
                text=target_memory.summary,
                target_language=target_lang,
                llm_provider=llm,
                model=model,
            )
            if target_memory.summary
            else None
        )
        translated_tags = list(target_memory.tags)
        if target_memory.tags:
            raw_tags = trans_service.translate_text_or_none(
                text=", ".join(target_memory.tags),
                target_language=target_lang,
                llm_provider=llm,
                model=model,
            )
            if raw_tags:
                from shared.utils import parse_tags
                parsed = parse_tags(raw_tags)
                if parsed:
                    translated_tags = parsed
    except Exception as exc:
        logger.exception("LLM memory translation failed for session %s, memory %s: %s", session_id, memory_id, exc)
        return jsonify({"error": "LLM memory translation failed."}), 502

    new_title = translated_title or target_memory.title
    new_summary = translated_summary or target_memory.summary
    if target_memory.summary and translated_summary is None and translated_title is None:
        return jsonify({"error": "Translation failed. Please check the Assistant LLM."}), 502

    try:
        mem_service.update_memory(
            memory=target_memory,
            title=new_title,
            tags=translated_tags,
            summary=new_summary,
        )
        mem_repo.update_memory(target_memory)
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "id": target_memory.id,
            "chat_session_id": target_memory.chat_session_id,
            "message_idx": target_memory.message_idx,
            "title": target_memory.title,
            "tags": target_memory.tags,
            "summary": target_memory.summary,
            "target_language": target_lang,
        }
    )
