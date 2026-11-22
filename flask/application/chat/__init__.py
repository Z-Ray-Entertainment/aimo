from flask import Blueprint

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

from application.chat import memory_views, views  # noqa: E402, F401

__all__ = ["chat_bp"]
