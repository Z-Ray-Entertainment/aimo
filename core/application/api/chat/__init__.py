from flask import Blueprint

api_chat_bp = Blueprint("api_chat", __name__, url_prefix="/api/chat")

from application.api.chat.shared import has_active_chat_tasks  # noqa: E402
from application.api.chat import (  # noqa: E402, F401
    lorebooks,
    memories,
    messages,
    misc,
    sessions,
    streaming,
    world_media,
)

__all__ = ["api_chat_bp", "has_active_chat_tasks"]
