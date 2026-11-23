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
from infrastructure.repositories.relationship_repository import RelationshipRepository
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

        origin_language = (
            str(data.get("origin_language") or user.language or "en").strip().lower()[:2] or "en"
        )
        raw_source = data if request.is_json else request.form
        dialogue_examples = data.get("dialogue_examples", [])
        if not isinstance(dialogue_examples, list):
            if data.get("dialogue_examples_json"):
                try:
                    parsed_ex = json.loads(data["dialogue_examples_json"])
                    dialogue_examples = parsed_ex if isinstance(parsed_ex, list) else []
                except (json.JSONDecodeError, TypeError):
                    dialogue_examples = []
            else:
                dialogue_examples = [
                    line.strip()
                    for line in str(dialogue_examples).splitlines()
                    if line.strip()
                ]

        lorebook_world_conditions: dict[int, int] = {}
        raw_cond = data.get("lorebook_world_conditions")
        if not isinstance(raw_cond, dict) and data.get("lorebook_world_conditions_json"):
            try:
                raw_cond = json.loads(data["lorebook_world_conditions_json"])
            except (json.JSONDecodeError, TypeError):
                raw_cond = {}
        if isinstance(raw_cond, dict):
            for k, v in raw_cond.items():
                if str(k).isdigit() and str(v).isdigit() and int(v) > 0:
                    lorebook_world_conditions[int(k)] = int(v)

        raw_collab = data.get("collaborator_creator_tags")
        if isinstance(raw_collab, list):
            collaborator_tags = [str(t).strip().lower() for t in raw_collab if str(t).strip()]
        else:
            collaborator_tags = [t.strip().lower() for t in str(raw_collab or "").split(",") if t.strip()]

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
            origin_language=origin_language,
            dialogue_examples=dialogue_examples,
            linked_lorebook_ids=RequestDataParser.to_int_list(raw_source, "linked_lorebook_ids"),
            lorebook_world_conditions=lorebook_world_conditions,
            suggested_worldinfo_id=RequestDataParser.to_opt_int(data, "suggested_worldinfo_id"),
            initial_location_id=RequestDataParser.to_opt_int(data, "initial_location_id"),
            initial_relationship=int(data.get("initial_relationship", 0)),
            preferred_location_ids=RequestDataParser.to_int_list(raw_source, "preferred_location_ids"),
            disliked_location_ids=RequestDataParser.to_int_list(raw_source, "disliked_location_ids"),
            collaborator_creator_tags=collaborator_tags,
        )
        saved = char_repo.save(character)
        if saved.id is not None:
            trans_repo = TranslationRepository()
            for field_name, param_name in (
                ("description", "i18n_description"),
                ("appearance", "i18n_appearance"),
                ("first_message", "i18n_first_message"),
            ):
                raw_variants = data.get(param_name)
                if isinstance(raw_variants, str) and raw_variants.strip():
                    trans_repo.save_field_variants_json("character", saved.id, field_name, raw_variants)
        return jsonify({"id": saved.id, "name": saved.name}), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400




@api_characters_bp.route("/<int:character_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def duplicate_character(character_id: int):
    user = get_current_user()
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


@api_characters_bp.route("/relationship-tiers", methods=["GET"])
@require_auth
def list_relationship_tiers():
    user = get_current_user()
    lang = (user.language or "en")[:2].lower()
    tiers = RelationshipRepository().list_tiers(lang)
    return jsonify({"tiers": [{"level": t.level, "name": t.name} for t in tiers]})


@api_characters_bp.route("/<int:character_id>", methods=["GET"])
@require_auth
def get_character_detail(character_id: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Character not found."}), 404
    events = WorldInfoRepository().list_character_events(character_id)
    i18n_map = TranslationRepository().get_entity_translations_map("character", char.id)
    return jsonify(
        {
            "id": char.id,
            "user_id": char.user_id,
            "name": char.name,
            "gender": char.gender.value,
            "visibility": char.visibility,
            "origin_language": char.origin_language,
            "primary_portrait_path": char.primary_portrait_path,
            "avatar_path": char.avatar_path,
            "card_image_path": char.card_image_path,
            "appearance": char.appearance,
            "description": char.description,
            "first_message": char.first_message,
            "dialogue_examples": char.dialogue_examples,
            "linked_lorebook_ids": char.linked_lorebook_ids,
            "lorebook_world_conditions": char.lorebook_world_conditions,
            "suggested_worldinfo_id": char.suggested_worldinfo_id,
            "initial_location_id": char.initial_location_id,
            "initial_relationship": char.initial_relationship,
            "preferred_location_ids": char.preferred_location_ids,
            "disliked_location_ids": char.disliked_location_ids,
            "collaborator_creator_tags": char.collaborator_creator_tags,
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
            "events": [_serialize_character_event(ev) for ev in events],
            "i18n": i18n_map,
            "editable": char.is_editable_by_user(user.id, is_admin(), user.creator_tag),
            "deletable": char.is_deletable_by_user(user.id, is_admin()),
        }
    )


@api_characters_bp.route("/<int:character_id>", methods=["PUT"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def update_character_detail(character_id: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404
    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        raw_cond = data.get("lorebook_world_conditions")
        lorebook_world_conditions = None
        if isinstance(raw_cond, dict):
            lorebook_world_conditions = {
                int(k): int(v)
                for k, v in raw_cond.items()
                if str(k).isdigit() and str(v).isdigit() and int(v) > 0
            }

        suggested_wi = (
            RequestDataParser.to_opt_int(data, "suggested_worldinfo_id")
            if "suggested_worldinfo_id" in data
            else char.suggested_worldinfo_id
        )
        initial_loc = (
            RequestDataParser.to_opt_int(data, "initial_location_id")
            if "initial_location_id" in data
            else char.initial_location_id
        )

        updated = CharacterService().update_character(
            char,
            name=data.get("name", char.name),
            gender=data.get("gender", char.gender.value),
            primary_portrait_path=data.get("primary_portrait_path", char.primary_portrait_path),
            description=data.get("description", char.description),
            first_message=data.get("first_message", char.first_message),
            visibility=data.get("visibility", char.visibility),
            appearance=data.get("appearance", char.appearance),
            dialogue_examples=(
                data["dialogue_examples"]
                if "dialogue_examples" in data and isinstance(data["dialogue_examples"], list)
                else None
            ),
            linked_lorebook_ids=(
                RequestDataParser.to_int_list(data, "linked_lorebook_ids")
                if "linked_lorebook_ids" in data
                else None
            ),
            lorebook_world_conditions=lorebook_world_conditions,
            suggested_worldinfo_id=suggested_wi,
            initial_location_id=initial_loc,
            initial_relationship=int(data.get("initial_relationship", char.initial_relationship)),
            preferred_location_ids=(
                RequestDataParser.to_int_list(data, "preferred_location_ids")
                if "preferred_location_ids" in data
                else None
            ),
            disliked_location_ids=(
                RequestDataParser.to_int_list(data, "disliked_location_ids")
                if "disliked_location_ids" in data
                else None
            ),
            collaborator_creator_tags=(
                data["collaborator_creator_tags"]
                if "collaborator_creator_tags" in data and isinstance(data["collaborator_creator_tags"], list)
                else None
            ),
        )
        saved = char_repo.save(updated)
        if saved.id is not None:
            trans_repo = TranslationRepository()
            for field_name, param_name in (
                ("description", "i18n_description"),
                ("appearance", "i18n_appearance"),
                ("first_message", "i18n_first_message"),
            ):
                raw_variants = data.get(param_name)
                if isinstance(raw_variants, str) and raw_variants.strip():
                    trans_repo.save_field_variants_json("character", saved.id, field_name, raw_variants)
        return jsonify({"id": saved.id, "name": saved.name})
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_characters_bp.route("/<int:character_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHARACTER_DELETE)
def delete_character_detail(character_id: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_deletable_by_user(user.id, is_admin()):
        return jsonify({"error": "Character not found."}), 404
    return jsonify({"deleted": char_repo.delete(character_id)})


