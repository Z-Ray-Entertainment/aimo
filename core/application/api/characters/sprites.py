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


