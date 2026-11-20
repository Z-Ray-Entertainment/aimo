import json
import re

from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, is_admin, require_auth, require_permission
from application.character_helpers import save_and_persist_sprite
from application.translation_helpers import is_character_ready_for_language
from domain.characters.models import Emotion, Gender
from domain.characters.services import CharacterService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters
from domain.translation.models import LANGUAGE_METADATA
from domain.worldinfo.services import WorldInfoService
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError
from shared.llm_activity import interactive_llm_guard
from shared.request_parsers import RequestDataParser


from application.api.characters import api_characters_bp

def _parse_opt_rel_int(data, key: str) -> int | None:
    if not hasattr(data, "get"):
        return None
    raw = data.get(key)
    if raw in (None, "", "none"):
        return None
    if isinstance(raw, bool):
        raise ValueError(f"{key} must be an integer tier value.")
    return int(raw)


def _serialize_character_event(ev) -> dict:
    return {
        "id": ev.id,
        "character_id": ev.character_id,
        "worldinfo_id": ev.worldinfo_id,
        "location_id": ev.location_id,
        "title": ev.title,
        "probability": ev.probability,
        "one_shot": ev.one_shot,
        "description": ev.description,
        "min_relationship": ev.min_relationship,
        "max_relationship": ev.max_relationship,
    }


def _validate_character_event_location(
    wi_repo: WorldInfoRepository,
    location_id: int | None,
    character,
    user_id: int,
    user_is_admin: bool,
) -> tuple[bool, str | None]:
    if location_id is None:
        return True, None
    if not character.suggested_worldinfo_id:
        return False, "Character has no recommended WorldInfo configured for location-bound events."
    loc = wi_repo.get_location(location_id)
    if loc is None or loc.worldinfo_id != character.suggested_worldinfo_id:
        return False, "Location does not belong to the character's recommended WorldInfo."
    wi = wi_repo.get_by_id(loc.worldinfo_id)
    if wi is None or not wi.is_visible_to_user(user_id, user_is_admin):
        return False, "Location not found."
    if not loc.is_accessible_by_character(character.id):
        return False, "Location is bound to a different character."
    return True, None


@api_characters_bp.route("/<int:character_id>/events", methods=["GET"])
@require_auth
def list_character_events(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Character not found."}), 404

    wi_repo = WorldInfoRepository()
    events = wi_repo.list_character_events(character_id)
    return jsonify({"events": [_serialize_character_event(ev) for ev in events]})


@api_characters_bp.route("/<int:character_id>/events", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def create_character_event(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    wi_repo = WorldInfoRepository()
    wi_service = WorldInfoService()
    location_id = RequestDataParser.to_opt_int(data, "location_id")
    ok, err_msg = _validate_character_event_location(wi_repo, location_id, character, user.id, is_admin())
    if not ok:
        return jsonify({"error": err_msg}), 400

    try:
        ev = wi_service.add_event(
            worldinfo_id=None,
            character_id=character_id,
            title=RequestDataParser.to_str(data, "title"),
            description=RequestDataParser.to_str(data, "description"),
            probability=RequestDataParser.to_int(data, "probability", default=50),
            one_shot=RequestDataParser.to_bool(data, "one_shot"),
            location_id=location_id,
            min_relationship=_parse_opt_rel_int(data, "min_relationship"),
            max_relationship=_parse_opt_rel_int(data, "max_relationship"),
        )
        saved = wi_repo.add_event(ev)
        return jsonify(_serialize_character_event(saved)), 201
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_characters_bp.route("/<int:character_id>/events/<int:event_id>", methods=["PUT"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def update_character_event(character_id: int, event_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404

    wi_repo = WorldInfoRepository()
    ev = wi_repo.get_event(event_id)
    if ev is None or ev.character_id != character_id:
        return jsonify({"error": "Event not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    wi_service = WorldInfoService()
    location_id = RequestDataParser.to_opt_int(data, "location_id")
    ok, err_msg = _validate_character_event_location(wi_repo, location_id, character, user.id, is_admin())
    if not ok:
        return jsonify({"error": err_msg}), 400

    try:
        wi_service.update_event(
            event=ev,
            title=RequestDataParser.to_str(data, "title"),
            description=RequestDataParser.to_str(data, "description"),
            probability=RequestDataParser.to_int(data, "probability", default=50),
            one_shot=RequestDataParser.to_bool(data, "one_shot"),
            location_id=location_id,
            min_relationship=_parse_opt_rel_int(data, "min_relationship"),
            max_relationship=_parse_opt_rel_int(data, "max_relationship"),
        )
        saved = wi_repo.update_event(ev)
        return jsonify(_serialize_character_event(saved))
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_characters_bp.route("/<int:character_id>/events/<int:event_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_character_event(character_id: int, event_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404

    wi_repo = WorldInfoRepository()
    ev = wi_repo.get_event(event_id)
    if ev is None or ev.character_id != character_id:
        return jsonify({"error": "Event not found."}), 404

    deleted = wi_repo.delete_event(event_id)
    return jsonify({"deleted": deleted})
