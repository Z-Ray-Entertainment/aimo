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
from application.api.characters.events import _serialize_character_event

@api_characters_bp.route("", methods=["GET"])
@require_auth
def list_characters():
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
    trans_repo = TranslationRepository()
    user_lang = (user.language or "en")[:2].lower()
    characters = char_repo.list_visible(user.id)

    gender_filter = request.args.get("gender", "").strip().lower()
    chat_filter = request.args.get("chatted", "").strip().lower()
    author_filter = (
        request.args.get("author", "").strip().lower()
        or request.args.get("scope", "").strip().lower()
    )

    result = []
    for char in characters:
        if char.id is None:
            continue
        is_editable = char.is_editable_by_user(user.id, is_admin(), user.creator_tag)
        is_ready = is_character_ready_for_language(char, user_lang, trans_repo, wi_repo)
        if not is_ready and not is_editable:
            continue
        if author_filter in ("mine", "own") and char.user_id != user.id:
            continue
        if author_filter in ("collaborations", "collab"):
            is_collab = (
                char.user_id != user.id
                and bool(user.creator_tag)
                and (user.creator_tag in (getattr(char, "collaborator_creator_tags", []) or []))
            )
            if not is_collab:
                continue
        if gender_filter and char.gender.value != gender_filter:
            continue
        msg_count = char_repo.get_message_count_for_user(char.id, user.id)
        if chat_filter == "yes" and msg_count == 0:
            continue
        if chat_filter == "no" and msg_count > 0:
            continue
        best_rel = char_repo.get_best_relationship_for_user(
            char.id, user.id, default_value=float(char.initial_relationship)
        )
        result.append(
            {
                "id": char.id,
                "user_id": char.user_id,
                "name": char.name,
                "gender": char.gender.value,
                "visibility": char.visibility,
                "primary_portrait_path": char.primary_portrait_path,
                "avatar_path": char.avatar_path,
                "card_image_path": char.card_image_path,
                "appearance": trans_repo.get_localized_field("character", char.id, "appearance", user_lang, getattr(char, "appearance", "")),
                "description": trans_repo.get_localized_field("character", char.id, "description", user_lang, char.description),
                "first_message": trans_repo.get_localized_field("character", char.id, "first_message", user_lang, char.first_message),
                "translation_pending": not is_ready,
                "suggested_worldinfo_id": char.suggested_worldinfo_id,
                "initial_location_id": char.initial_location_id,
                "initial_relationship": char.initial_relationship,
                "best_relationship": best_rel,
                "message_count": msg_count,
                "sprites": [
                    {
                        "id": sp.id,
                        "emotion": sp.emotion.value,
                        "variant": sp.variant,
                        "file_path": sp.file_path,
                    }
                    for sp in char.sprites
                ],
                "gallery_images": [
                    {
                        "id": img.id,
                        "file_path": img.file_path,
                        "unlock_threshold": img.unlock_threshold,
                    }
                    for img in char.gallery_images
                ],
                "events": [
                    _serialize_character_event(ev)
                    for ev in wi_repo.list_character_events(char.id)
                ],
            }
        )
    return jsonify({"characters": result})


@api_characters_bp.route("", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def create_character():
    user = get_current_user()
    assert user is not None and user.id is not None
    char_service = CharacterService()
    char_repo = CharacterRepository()
    storage = FileStorage()

    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            portrait_path = data.get("primary_portrait_path", "portraits/default.png")
            avatar_path = data.get("avatar_path")
            card_image_path = data.get("card_image_path")
        else:
            data = request.form.to_dict()
            portrait_file = request.files.get("primary_portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
            else:
                portrait_path = data.get("primary_portrait_path", "portraits/default.png")

            avatar_file = request.files.get("avatar_portrait")
            if avatar_file and avatar_file.filename:
                avatar_path = storage.save_portrait(avatar_file.stream, avatar_file.filename)
            else:
                avatar_path = data.get("avatar_path")

            card_file = request.files.get("card_portrait")
            if card_file and card_file.filename:
                card_image_path = storage.save_portrait(card_file.stream, card_file.filename)
            else:
                card_image_path = data.get("card_image_path")

        character = char_service.create_character(
            user_id=user.id,
            name=data.get("name", ""),
            gender=data.get("gender", Gender.FEMALE.value),
            primary_portrait_path=portrait_path,
            avatar_path=avatar_path,
            card_image_path=card_image_path,
            appearance=data.get("appearance", ""),
            description=data.get("description", ""),
            first_message=data.get("first_message", ""),
            visibility=data.get("visibility", "private"),
            dialogue_examples=(
                data.get("dialogue_examples", [])
                if isinstance(data.get("dialogue_examples"), list)
                else [
                    line.strip()
                    for line in str(data.get("dialogue_examples", "")).splitlines()
                    if line.strip()
                ]
            ),
            linked_lorebook_ids=[
                int(x) for x in data.get("linked_lorebook_ids", []) if str(x).isdigit()
            ],
            suggested_worldinfo_id=(
                int(data["suggested_worldinfo_id"])
                if data.get("suggested_worldinfo_id")
                else None
            ),
            initial_location_id=(
                int(data["initial_location_id"])
                if data.get("initial_location_id")
                else None
            ),
            initial_relationship=int(data.get("initial_relationship", 0)),
        )
        saved = char_repo.save(character)
        return jsonify({"id": saved.id, "name": saved.name}), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400




@api_characters_bp.route("/<int:character_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def duplicate_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    orig = char_repo.get_by_id(character_id)
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Character not found."}), 404
    if not orig.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        trans_repo = TranslationRepository()
        user_lang = (user.language or "en")[:2].lower()
        if not is_character_ready_for_language(orig, user_lang, trans_repo):
            return jsonify({"error": "This character is not yet available in your language."}), 403
    copied = char_repo.duplicate(character_id, user.id)
    return jsonify({"id": copied.id, "name": copied.name}), 201


