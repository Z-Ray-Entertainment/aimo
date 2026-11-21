from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify

from application.api.auth import get_current_user, is_admin
from application.chat_services.task_registry import (
    _ACTIVE_IMAGE_TASKS,
    _ADMIN_PROMPT_CACHE,
    _BACKGROUND_TASKS,
    _TASKS_LOCK,
    _USER_NOTIFICATIONS,
    BackgroundTurnTask as _BackgroundTurnTask,
    extract_active_tags as _extract_active_tags,
    has_active_chat_tasks,
    record_admin_prompt as _record_admin_prompt,
)
from domain.chat.models import ChatSession
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository


def _get_authorized_session(session_id: int, user) -> tuple[ChatSession | None, bool]:
    if user is None or user.id is None:
        return None, False
    chat_session = ChatRepository().get_session(session_id)
    if chat_session is None or not chat_session.is_visible_to_user(user.id, False):
        return None, False
    admin_flag = is_admin()
    character = CharacterRepository().get_by_id(chat_session.character_id)
    if character is None or not character.is_visible_to_user(user.id, admin_flag):
        return None, False
    return chat_session, admin_flag


def require_chat_session(view_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view_func)
    def wrapped(session_id: int, *args: Any, **kwargs: Any) -> Any:
        user = get_current_user()
        assert user is not None and user.id is not None
        chat_session, admin_flag = _get_authorized_session(session_id, user)
        if chat_session is None:
            return jsonify({"error": "Session not found."}), 404
        return view_func(session_id, *args, user=user, chat_session=chat_session, is_admin=admin_flag, **kwargs)

    return wrapped
