from flask import Blueprint

api_characters_bp = Blueprint("api_characters", __name__, url_prefix="/api/characters")

from application.api.characters import ai_assist, events, routes, sprites  # noqa: E402, F401

__all__ = ["api_characters_bp"]
