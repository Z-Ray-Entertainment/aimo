import re

from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, is_admin, require_auth, require_permission
from application.character_helpers import save_and_persist_sprite
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
    author_filter = (
        request.args.get("author", "").strip().lower()
        or request.args.get("scope", "").strip().lower()
    )

    result = []
    for char in characters:
        if char.id is None:
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
                "appearance": getattr(char, "appearance", ""),
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


def _clean_sparkle_prose(raw_text: str) -> str:
    cleaned = re.sub(
        r"<(?:think|thought|reasoning|scratchpad)>.*?</(?:think|thought|reasoning|scratchpad)>",
        "",
        raw_text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    if not cleaned:
        cleaned = re.sub(
            r"<(?:think|thought|reasoning|scratchpad)>.*",
            "",
            raw_text,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip() or raw_text

    cleaned = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", cleaned, flags=re.MULTILINE)

    cleaned_lines: list[str] = []
    for line in cleaned.splitlines():
        l = line.strip()
        if not l:
            cleaned_lines.append("")
            continue
        l = re.sub(r"^>+\s*", "", l)
        l = re.sub(r"^#+\s*", "", l)
        l = re.sub(r"^[-*+•]\s+", "", l)
        l = re.sub(r"^\d+[\.)]\s+", "", l)
        cleaned_lines.append(l)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\w)_{1,3}(.*?)_{1,3}(?!\w)", r"\1", cleaned)
    cleaned = re.sub(r"`+(.*?)`+", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


@api_characters_bp.route("/sparkle", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT, FunctionPermission.CHARACTER_CREATE)
def sparkle_description():
    data = request.get_json(silent=True) or {}
    draft = str(data.get("description", "")).strip()
    name = str(data.get("name", "Character")).strip()
    gender = str(data.get("gender", "")).strip()
    gender_info = f"\nGender: {gender}" if gender else ""

    settings = SettingsRepository().get_settings()
    llm_provider = get_llm_provider(settings)
    prompt = (
        f"{settings.prompts.sparkle_assistant_prompt}\n\n"
        f"Character Name: {name}{gender_info}\n"
        f"Draft / Notes:\n{draft or 'Create an engaging fantasy/roleplay personality.'}\n\n"
        "Strict Formatting & Persona Rules:\n"
        f"- Focus entirely on defining {name} (or {{{{char}}}}): establish their identity, psychology, temperament, mannerisms, and worldview so the roleplay model effortlessly embodies this persona as its own self.\n"
        "- Write strictly in natural, continuous narrative prose paragraphs (pure prose).\n"
        "- Do NOT use any markdown formatting, headings, bullet points, numbered lists, bold text, or asterisks.\n"
        "- Do NOT include meta-text, introductions, or instructions; output only the final character description."
    )
    try:
        raw_output = llm_provider.generate(
            prompt=prompt,
            model=settings.tasks.assistant_model,
            params=ModelParameters(
                num_ctx=settings.params.num_ctx,
                temperature=0.75,
                top_p=0.9,
                repeat_penalty=1.1,
            ),
            think=False,
        ).strip()
        improved = _clean_sparkle_prose(raw_output)
        return jsonify({"description": improved})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502


@api_characters_bp.route("/extract-appearance", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT, FunctionPermission.CHARACTER_CREATE)
def extract_appearance():
    storage = FileStorage()
    portrait_path = None

    if "primary_portrait" in request.files and request.files["primary_portrait"].filename:
        file = request.files["primary_portrait"]
        portrait_path = storage.save_portrait(file.stream, file.filename)
    elif "portrait" in request.files and request.files["portrait"].filename:
        file = request.files["portrait"]
        portrait_path = storage.save_portrait(file.stream, file.filename)
    elif request.is_json:
        data = request.get_json(silent=True) or {}
        char_id = data.get("character_id")
        if char_id:
            char = CharacterRepository().get_by_id(int(char_id))
            if char:
                portrait_path = char.primary_portrait_path
        if not portrait_path:
            portrait_path = data.get("portrait_path")
    else:
        char_id = request.form.get("character_id")
        if char_id:
            char = CharacterRepository().get_by_id(int(char_id))
            if char:
                portrait_path = char.primary_portrait_path
        if not portrait_path:
            portrait_path = request.form.get("portrait_path")

    if not portrait_path:
        return jsonify({"error": "Bitte lade zuerst ein Porträtbild hoch."}), 400

    resolved_path = storage.resolve_path(portrait_path)
    if not resolved_path.is_file():
        return jsonify({"error": "Kein gültiges Porträtbild zum Analysieren vorhanden."}), 400

    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    prompt = (
        f"{settings.prompts.vision_persona_prompt.strip()}\n"
        "Focus strictly on physical traits: face, eyes, hair, skin tone, clothing, and physique. "
        "Keep it concise and descriptive."
    )
    try:
        appearance = llm.analyze_image(
            image_path=resolved_path,
            prompt=prompt,
            model=settings.tasks.vision_model,
        ).strip()
        return jsonify({"appearance": appearance, "portrait_path": portrait_path})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        return jsonify({"error": f"Bildanalyse fehlgeschlagen: {exc}"}), 502


@api_characters_bp.route("/<int:character_id>/sprites", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

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
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Character not found."}), 404
    deleted = char_repo.delete_sprite(character_id, emotion, variant)
    return jsonify({"deleted": deleted})


@api_characters_bp.route("/<int:character_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def duplicate_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    orig = char_repo.get_by_id(character_id)
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Character not found."}), 404
    copied = char_repo.duplicate(character_id, user.id)
    return jsonify({"id": copied.id, "name": copied.name}), 201
