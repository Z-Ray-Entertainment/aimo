from __future__ import annotations

from flask import Blueprint, jsonify

from application.api.auth import is_admin, require_auth
from application.api.helpers import require_current_user
from application.translation_helpers import (
    is_character_ready_for_language,
    is_lorebook_ready_for_language,
    is_worldinfo_ready_for_language,
)
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository

api_overview_bp = Blueprint("api_overview", __name__, url_prefix="/api/overview")


@api_overview_bp.route("", methods=["GET"])
@require_auth
def get_overview():
    user = require_current_user()
    assert user.id is not None
    admin_flag = is_admin()
    user_lang = (user.language or "en")[:2].lower()
    trans_repo = TranslationRepository()
    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
    lb_repo = LorebookRepository()
    chat_repo = ChatRepository()

    characters = []
    for char in char_repo.list_visible(user.id):
        editable = char.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        if not editable and not is_character_ready_for_language(char, user_lang, trans_repo):
            continue
        characters.append(
            {
                "id": char.id,
                "name": char.name,
                "visibility": char.visibility,
                "primary_portrait_path": char.primary_portrait_path,
                "avatar_path": char.avatar_path,
                "card_image_path": char.card_image_path,
                "editable": editable,
                "deletable": char.is_deletable_by_user(user.id, admin_flag),
            }
        )

    worldinfos = []
    for wi in wi_repo.list_visible(user.id):
        editable = wi.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        if not editable and not is_worldinfo_ready_for_language(wi, user_lang, trans_repo, wi_repo):
            continue
        worldinfos.append(
            {
                "id": wi.id,
                "name": wi.name,
                "icon": wi.icon,
                "visibility": wi.visibility,
                "cover_image_path": wi.cover_image_path,
                "editable": editable,
                "deletable": wi.is_deletable_by_user(user.id, admin_flag),
            }
        )

    lorebooks = []
    for lb in lb_repo.list_visible(user.id):
        editable = lb.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        if not editable and not is_lorebook_ready_for_language(lb, user_lang, trans_repo, lb_repo):
            continue
        lorebooks.append(
            {
                "id": lb.id,
                "name": lb.name,
                "description": lb.description,
                "visibility": lb.visibility,
                "editable": editable,
                "deletable": lb.is_deletable_by_user(user.id, admin_flag),
            }
        )

    sessions = [
        {
            "id": sess.id,
            "title": sess.title,
            "character_id": sess.character_id,
            "persona_id": sess.persona_id,
            "active_worldinfo_id": sess.active_worldinfo_id,
            "last_message_at": sess.last_message_at.isoformat(),
        }
        for sess in chat_repo.list_all_sessions_for_user(user.id)
    ]

    return jsonify(
        {
            "characters": characters,
            "worldinfos": worldinfos,
            "lorebooks": lorebooks,
            "sessions": sessions,
        }
    )
