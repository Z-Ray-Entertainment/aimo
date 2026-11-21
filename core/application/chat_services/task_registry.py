from __future__ import annotations

import re
import threading
import uuid

from domain.chat.models import Message
from shared.llm_activity import is_interactive_llm_busy
from shared.utils import filter_stopwords, parse_tags

_ACTIVE_IMAGE_TASKS: dict[int, str] = {}


class BackgroundTurnTask:
    def __init__(
        self,
        session_id: int,
        user_id: int,
        user_language: str = "en",
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
_BACKGROUND_TASKS: dict[int, BackgroundTurnTask] = {}
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


def record_admin_prompt(session_id: int, message_idx: int, prompt: str) -> None:
    with _TASKS_LOCK:
        if len(_ADMIN_PROMPT_CACHE) >= _ADMIN_PROMPT_MAX_ENTRIES:
            oldest_key = next(iter(_ADMIN_PROMPT_CACHE))
            _ADMIN_PROMPT_CACHE.pop(oldest_key, None)
        _ADMIN_PROMPT_CACHE[(session_id, message_idx)] = prompt


def extract_active_tags(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9äöüÄÖÜß_-]{3,}", text.lower())
    clean_words = filter_stopwords(words)
    return parse_tags(clean_words)
