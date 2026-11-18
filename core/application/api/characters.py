import json
import re

from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, is_admin, require_auth, require_permission
from application.character_helpers import save_and_persist_sprite
from domain.characters.models import Emotion, Gender
from domain.characters.services import CharacterService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters
from domain.worldinfo.services import WorldInfoService
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError
from shared.request_parsers import RequestDataParser

api_characters_bp = Blueprint("api_characters", __name__, url_prefix="/api/characters")


@api_characters_bp.route("", methods=["GET"])
@require_auth
def list_characters():
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
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


def _parse_dialogue_pair(
    raw_text: str,
    current_trigger: str = "",
    character_name: str = "",
) -> tuple[str, str]:
    text = raw_text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()

    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            t = str(data.get("trigger", "")).strip()
            r = str(data.get("response", "")).strip()
            if r:
                return (t or current_trigger, r)
        except Exception:
            pass

    if character_name:
        text = re.sub(rf"(?im)^\s*{re.escape(character_name)}\s*:", "{{char}}:", text)

    if "<START>" in text:
        parts = text.split("<START>", 1)
        text = parts[1].strip()

    trigger = current_trigger.strip()
    response = ""

    user_match = re.search(r"(?im)^\s*\{\{user\}\}\s*:\s*(.+)$", text, re.MULTILINE)
    char_match = re.search(r"(?im)^\s*\{\{char\}\}\s*:\s*(.+)$", text, re.MULTILINE)

    if user_match and char_match:
        user_pos = user_match.start()
        char_pos = char_match.start()
        if user_pos < char_pos:
            u_block = text[user_pos:char_pos].strip()
            u_line = re.sub(r"(?im)^\s*\{\{user\}\}\s*:\s*", "", u_block).strip()
            if not trigger:
                trigger = u_line
            r_block = text[char_pos:].strip()
            response = re.sub(r"(?im)^\s*\{\{char\}\}\s*:\s*", "", r_block).strip()
        else:
            trigger = user_match.group(1).strip()
            response = char_match.group(1).strip()
    elif char_match:
        char_pos = char_match.start()
        if not trigger and char_pos > 0:
            pre_text = text[:char_pos].strip()
            trigger = re.sub(r"(?im)^\s*\{\{user\}\}\s*:\s*", "", pre_text).strip()
        response = re.sub(r"(?im)^\s*\{\{char\}\}\s*:\s*", "", text[char_pos:]).strip()
    else:
        if trigger:
            response = text
        else:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if len(lines) >= 2:
                trigger = lines[0]
                response = "\n".join(lines[1:])
            elif lines:
                response = lines[0]

    trigger = re.sub(r"(?im)^\s*\{\{user\}\}\s*:\s*", "", trigger).strip()
    response = re.sub(r"(?im)^\s*\{\{char\}\}\s*:\s*", "", response).strip()
    return trigger, response


@api_characters_bp.route("/sparkle-dialogue", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT, FunctionPermission.CHARACTER_CREATE)
def sparkle_dialogue():
    data = request.get_json(silent=True) or {}
    description = str(data.get("description", "")).strip()
    if not description or len(description) < 10:
        return (
            jsonify({"error": "Bitte gib zuerst eine aussagekräftige Charakterbeschreibung im Reiter 'Basis-Info' ein."}),
            400,
        )

    name = str(data.get("name", "Character")).strip() or "Character"
    gender = str(data.get("gender", "")).strip()
    language = str(data.get("language", "de")).strip() or "de"
    current_trigger = str(data.get("current_trigger", "")).strip()
    current_response = str(data.get("current_response", "")).strip()
    existing_examples = data.get("existing_examples", [])

    existing_context = ""
    if isinstance(existing_examples, list) and existing_examples:
        rendered_existing = []
        for idx, ex in enumerate(existing_examples[:6], 1):
            if isinstance(ex, dict):
                t = str(ex.get("trigger", "")).strip()
                r = str(ex.get("response", "")).strip()
                if t or r:
                    rendered_existing.append(f"Example {idx}:\n{{{{user}}}}: {t}\n{{{{char}}}}: {r}")
        if rendered_existing:
            existing_context = (
                "\n\nExisting dialogue examples (do NOT repeat these situations or topics):\n"
                + "\n\n".join(rendered_existing)
            )

    gender_info = f"\nGender: {gender}" if gender else ""

    if current_trigger:
        task_instruction = (
            f"The player provided this specific trigger prompt:\n"
            f"{{{{user}}}}: {current_trigger}\n\n"
            f"Your task: Write exclusively {{{{char}}}}'s natural in-character response to this trigger, "
            f"embodying {name}'s personality, temperament, mood, and quirks from the description."
        )
    elif current_response:
        task_instruction = (
            f"The author provided a rough response draft:\n"
            f"{current_response}\n\n"
            f"Your task: Refine this into an authentic, in-character response for {{{{char}}}} and invent a "
            f"fitting {{{{user}}}} trigger prompt that provokes this reaction."
        )
    else:
        task_instruction = (
            f"Invent a fresh, vivid dialogue interaction between {{{{user}}}} and {{{{char}}}} showcasing "
            f"{name}'s speech mannerisms, worldview, and emotional tone."
        )

    settings = SettingsRepository().get_settings()
    llm_provider = get_llm_provider(settings)

    prompt = (
        f"{settings.prompts.dialogue_author_prompt}\n\n"
        f"Language Directive: The dialogue must be written in language '{language}'.\n"
        f"Character Name: {name}{gender_info}\n"
        f"Character Description:\n{description}"
        f"{existing_context}\n\n"
        f"Task:\n{task_instruction}\n\n"
        "Output Format Requirement:\n"
        "Output strictly ONE dialogue pair in this format:\n"
        "<START>\n"
        "{{user}}: <trigger line>\n"
        "{{char}}: <in-character response with *actions* and \"dialogue\">\n"
        "Rules:\n"
        "- Use {{user}} and {{char}} as placeholders.\n"
        "- Spoken words in quotation marks, actions/gestures in asterisks.\n"
        "- Do NOT add conversational meta-talk, notes, or markdown fences."
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
        parsed_trigger, parsed_response = _parse_dialogue_pair(
            raw_output,
            current_trigger=current_trigger,
            character_name=name,
        )
        return jsonify({"trigger": parsed_trigger, "response": parsed_response})
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
