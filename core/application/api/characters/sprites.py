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


@api_characters_bp.route("/<int:character_id>/sprites", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    user = get_current_user()

    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404

    emotion_raw = request.form.get("emotion", Emotion.NEUTRAL.value)
    emotion = Emotion.resolve(emotion_raw)
    sprite_file = request.files.get("sprite")
    if sprite_file is None or not sprite_file.filename:
        return jsonify({"error": "No sprite file provided."}), 400

    try:
        persisted = save_and_persist_sprite(
            character=character,
            emotion=emotion,
            file_stream=sprite_file.stream,
            filename=sprite_file.filename,
            char_service=char_service,
            char_repo=char_repo,
            storage=storage,
        )
        return jsonify(
            {
                "id": persisted.id,
                "emotion": persisted.emotion.value,
                "variant": persisted.variant,
                "file_path": persisted.file_path,
            }
        ), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_characters_bp.route("/<int:character_id>/sprites/<string:emotion>/<int:variant>", methods=["DELETE"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_sprite(character_id: int, emotion: str, variant: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404
    deleted = char_repo.delete_sprite(character_id, emotion, variant)
    return jsonify({"deleted": deleted})


@api_characters_bp.route("/<int:character_id>/gallery", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_gallery_image(character_id: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404

    img_file = request.files.get("gallery_image")
    if img_file is None or not img_file.filename:
        return jsonify({"error": "No gallery image provided."}), 400

    threshold = RequestDataParser.to_int(request.form, "unlock_threshold", default=0)
    try:
        saved_path = FileStorage().save_portrait(img_file.stream, img_file.filename)
        img_entity = CharacterService().add_gallery_image(character, saved_path, threshold)
        persisted = char_repo.add_gallery_image(character_id, img_entity)
        return jsonify(
            {
                "id": persisted.id,
                "file_path": persisted.file_path,
                "unlock_threshold": persisted.unlock_threshold,
            }
        ), 201
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_characters_bp.route("/<int:character_id>/gallery/<int:image_id>", methods=["PUT"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def update_gallery_image(character_id: int, image_id: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404
    if not any(img.id == image_id for img in character.gallery_images):
        return jsonify({"error": "Gallery image not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        threshold = RequestDataParser.to_int(data, "unlock_threshold", default=0)
        validated = CharacterService().validate_gallery_threshold(threshold)
        char_repo.update_gallery_image_threshold(image_id, validated)
        return jsonify({"id": image_id, "unlock_threshold": validated})
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_characters_bp.route("/<int:character_id>/gallery/<int:image_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_gallery_image(character_id: int, image_id: int):
    user = get_current_user()
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404
    if not any(img.id == image_id for img in character.gallery_images):
        return jsonify({"error": "Gallery image not found."}), 404
    return jsonify({"deleted": char_repo.delete_gallery_image(image_id)})


