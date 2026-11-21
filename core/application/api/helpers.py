from __future__ import annotations

from typing import Any

from flask import jsonify, request

from application.api.auth import get_current_user
from domain.auth.models import User
from domain.chat.models import Message


def require_current_user() -> User:
    user = get_current_user()
    assert user is not None and user.id is not None
    return user


def parse_request_payload() -> dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def serialize_system_message(msg: Message) -> dict[str, Any]:
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "message_idx": msg.message_idx,
        "role": msg.role.value,
        "system_type": msg.system_type,
        "english_content": msg.english_content,
        "localized_content": msg.localized_content,
        "metadata": msg.metadata,
        "created_at": msg.created_at.isoformat(),
    }


def json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status
