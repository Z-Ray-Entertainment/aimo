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


logger = logging.getLogger(__name__)

_ACTIVE_IMAGE_TASKS: dict[int, str] = {}
_PENDING_PROMPTS: dict[int, dict] = {}


class _BackgroundTurnTask:
    def __init__(
        self,
        session_id: int,
        user_id: int,
        user_language: str = "de",
        has_image: bool = False,
        user_message_idx: int = 0,
        is_admin: bool = False,
    ) -> None:
        self.task_id: str = uuid.uuid4().hex
        self.session_id: int = session_id
        self.user_id: int = user_id
        self.user_language: str = user_language
        self.has_image: bool = has_image
        self.user_message_idx: int = user_message_idx
        self.is_admin: bool = is_admin
        self.system_message: Message | None = None
        self.can_view_event_counter: bool = False
        self.can_debug_relationship: bool = False
        self.cooldown_counter: int | None = None
        self.events_enabled: bool = True
        self.assembled_prompt: str | None = None
        self.image_analyzed: bool = False
        self.image_alt_text: str | None = None
        self.condition: threading.Condition = threading.Condition()
        self.status: str = "analyzing_image" if has_image else "thinking"
        self.tokens: list[dict] = []
        self.english_reply: str = ""
        self.generation_done: bool = False
        self.result_payload: dict | None = None
        self.error_message: str | None = None
        self.delivered_via_stream: bool = False
        self.is_aborted: bool = False


_TASKS_LOCK = threading.Lock()
_BACKGROUND_TASKS: dict[int, _BackgroundTurnTask] = {}
_USER_NOTIFICATIONS: dict[int, list[dict]] = {}
_ADMIN_PROMPT_CACHE: dict[tuple[int, int], str] = {}
_ADMIN_PROMPT_MAX_ENTRIES: int = 150


def has_active_chat_tasks() -> bool:
    if is_interactive_llm_busy():
        return True
    with _TASKS_LOCK:
        return any(
            t.status in ("analyzing_image", "thinking", "streaming", "translating")
            and not t.is_aborted
            for t in _BACKGROUND_TASKS.values()
        )


def _record_admin_prompt(session_id: int, message_idx: int, prompt: str) -> None:
    with _TASKS_LOCK:
        if len(_ADMIN_PROMPT_CACHE) >= _ADMIN_PROMPT_MAX_ENTRIES:
            oldest_key = next(iter(_ADMIN_PROMPT_CACHE))
            _ADMIN_PROMPT_CACHE.pop(oldest_key, None)
        _ADMIN_PROMPT_CACHE[(session_id, message_idx)] = prompt


def _extract_active_tags(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9äöüÄÖÜß_-]{3,}", text.lower())
    clean_words = filter_stopwords(words)
    return parse_tags(clean_words)




def _get_authorized_session(session_id: int, user) -> tuple[ChatSession | None, bool]:
    if user is None or user.id is None:
        return None, False
    chat_repo = ChatRepository()
    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or chat_session.user_id != user.id:
        return None, False
    is_admin = bool(user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS))
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(chat_session.character_id)
    if character is None or not character.is_visible_to_user(user.id, is_admin):
        return None, False
    return chat_session, is_admin


