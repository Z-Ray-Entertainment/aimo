from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, require_auth, require_permission
from domain.characters.models import Emotion, Gender
from domain.characters.services import CharacterService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

api_characters_bp = Blueprint("api_characters", __name__, url_prefix="/api/characters")


@api_characters_bp.route("", methods=["GET"])
@require_auth
def list_characters():
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    characters = char_repo.list_visible(user.id)

    gender_filter = request.args.get("gender", "").strip().lower()
    chat_filter = request.args.get("chatted", "").strip().lower()

    result = []
    for char in characters:
        if char.id is None:
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
                "description": char.description,
                "first_message": char.first_message,
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
        else:
            data = request.form.to_dict()
            portrait_file = request.files.get("primary_portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
            else:
                portrait_path = data.get("primary_portrait_path", "portraits/default.png")

        character = char_service.create_character(
            user_id=user.id,
            name=data.get("name", ""),
            gender=data.get("gender", Gender.FEMALE.value),
            primary_portrait_path=portrait_path,
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


@api_characters_bp.route("/sparkle", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def sparkle_description():
    data = request.get_json(silent=True) or {}
    draft = str(data.get("description", "")).strip()
    name = str(data.get("name", "Character")).strip()

    settings = SettingsRepository().get_settings()
    llm_provider = get_llm_provider(settings)
    prompt = (
        f"{settings.prompts.sparkle_assistant_prompt}\n\n"
        f"Charaktername / Character Name: {name}\n"
        f"Vorlage / Draft:\n{draft or 'Create an engaging fantasy/roleplay personality.'}"
    )
    try:
        improved = llm_provider.generate(
            prompt=prompt,
            model=settings.tasks.assistant_model,
            params=ModelParameters(
                num_ctx=settings.params.num_ctx,
                temperature=0.75,
                top_p=0.9,
                repeat_penalty=1.1,
            ),
        ).strip()
        return jsonify({"description": improved})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502


@api_characters_bp.route("/<int:character_id>/sprites", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None:
        return jsonify({"error": "Character not found."}), 404

    emotion_raw = request.form.get("emotion", Emotion.NEUTRAL.value)
    emotion = Emotion.resolve(emotion_raw)
    sprite_file = request.files.get("sprite")
    if sprite_file is None or not sprite_file.filename:
        return jsonify({"error": "No sprite file provided."}), 400

    try:
        temp_sprite = char_service.add_sprite(character, emotion, "pending")
        saved_path = storage.save_sprite(
            character_id=character_id,
            content=sprite_file.stream,
            filename=sprite_file.filename,
            emotion=emotion.value,
            variant=temp_sprite.variant,
        )
        temp_sprite.file_path = saved_path
        persisted = char_repo.add_sprite(character_id, temp_sprite)
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
    char_repo = CharacterRepository()
    deleted = char_repo.delete_sprite(character_id, emotion, variant)
    return jsonify({"deleted": deleted})
