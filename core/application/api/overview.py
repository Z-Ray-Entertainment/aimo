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
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository

api_overview_bp = Blueprint("api_overview", __name__, url_prefix="/api/overview")


@api_overview_bp.route("", methods=["GET"])
@require_auth
def get_overview():
    user = require_current_user()
    admin_flag = is_admin()
    user_lang = (user.language or "en")[:2].lower()
    trans_repo = TranslationRepository()
    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
    lb_repo = LorebookRepository()
    chat_repo = ChatRepository()
    rel_repo = RelationshipRepository()
    has_missing_translations = False

    characters = []
    for char in char_repo.list_visible(user.id):
        if char.id is None:
            continue
        editable = char.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        is_ready = is_character_ready_for_language(char, user_lang, trans_repo, wi_repo)
        if not is_ready:
            has_missing_translations = True
            if not editable:
                continue
        msg_count = char_repo.get_message_count_for_user(char.id, user.id)
        best_rel = char_repo.get_best_relationship_for_user(
            char.id, user.id, default_value=float(char.initial_relationship)
        )
        tier = rel_repo.get_tier(best_rel, language=user_lang)
        description = trans_repo.get_localized_field(
            "character", char.id, "description", user_lang, char.description
        )
        characters.append(
            {
                "id": char.id,
                "user_id": char.user_id,
                "name": char.name,
                "gender": char.gender.value,
                "description": description,
                "visibility": char.visibility,
                "primary_portrait_path": char.primary_portrait_path,
                "avatar_path": char.avatar_path,
                "card_image_path": char.card_image_path,
                "collaborator_creator_tags": list(char.collaborator_creator_tags or []),
                "message_count": msg_count,
                "best_relationship": best_rel,
                "relationship_tier_name": tier.name,
                "translation_pending": not is_ready,
                "editable": editable,
                "deletable": char.is_deletable_by_user(user.id, admin_flag),
                "created_at": char.created_at.isoformat() if char.created_at else None,
            }
        )

    worldinfos = []
    for wi in wi_repo.list_visible(user.id):
        if wi.id is None:
            continue
        editable = wi.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        is_ready = is_worldinfo_ready_for_language(wi, user_lang, trans_repo, wi_repo)
        if not is_ready:
            has_missing_translations = True
            if not editable:
                continue
        location_count = len(wi_repo.list_locations(wi.id))
        event_count = len(wi_repo.list_events(wi.id))
        worldinfos.append(
            {
                "id": wi.id,
                "user_id": wi.user_id,
                "name": wi.name,
                "icon": wi.icon,
                "description": getattr(wi, "description", "") or "",
                "visibility": wi.visibility,
                "cover_image_path": wi.cover_image_path,
                "collaborator_creator_tags": list(wi.collaborator_creator_tags or []),
                "location_count": location_count,
                "event_count": event_count,
                "translation_pending": not is_ready,
                "editable": editable,
                "deletable": wi.is_deletable_by_user(user.id, admin_flag),
                "created_at": wi.created_at.isoformat() if wi.created_at else None,
            }
        )

    lorebooks = []
    for lb in lb_repo.list_visible(user.id):
        if lb.id is None:
            continue
        editable = lb.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        is_ready = is_lorebook_ready_for_language(lb, user_lang, trans_repo)
        if not is_ready:
            has_missing_translations = True
            if not editable:
                continue
        entry_count = len(lb_repo.list_entries(lb.id, user_id=user.id, is_admin=admin_flag))
        lorebooks.append(
            {
                "id": lb.id,
                "user_id": lb.user_id,
                "name": lb.name,
                "description": lb.description,
                "visibility": lb.visibility,
                "collaborator_creator_tags": list(lb.collaborator_creator_tags or []),
                "entry_count": entry_count,
                "translation_pending": not is_ready,
                "editable": editable,
                "deletable": lb.is_deletable_by_user(user.id, admin_flag),
                "created_at": lb.created_at.isoformat() if lb.created_at else None,
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
            "has_missing_translations": has_missing_translations,
        }
    )
