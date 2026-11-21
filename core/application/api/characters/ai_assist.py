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
    language = str(data.get("language", "en")).strip().lower()[:2] or "en"
    lang_meta = LANGUAGE_METADATA.get(language)
    lang_label = f"{lang_meta['label']} ({language})" if lang_meta else language
    gender_info = f"\nGender: {gender}" if gender else ""

    settings = SettingsRepository().get_settings()
    llm_provider = get_llm_provider(settings)
    prompt = (
        f"{settings.prompts.sparkle_assistant_prompt}\n\n"
        f"Language Directive: Write the entire character description strictly in {lang_label}.\n"
        f"Character Name: {name}{gender_info}\n"
        f"Draft / Notes:\n{draft or 'Create an engaging fantasy/roleplay personality.'}\n\n"
        "Strict Formatting & Persona Rules:\n"
        f"- Output strictly in {lang_label}, regardless of the language of the instructions.\n"
        f"- Focus entirely on defining {name} (or {{{{char}}}}): establish their identity, psychology, temperament, mannerisms, and worldview so the roleplay model effortlessly embodies this persona as its own self.\n"
        "- Write strictly in natural, continuous narrative prose paragraphs (pure prose).\n"
        "- Do NOT use any markdown formatting, headings, bullet points, numbered lists, bold text, or asterisks.\n"
        "- Do NOT include meta-text, introductions, or instructions; output only the final character description."
    )
    try:
        with interactive_llm_guard():
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
        with interactive_llm_guard():
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
            try:
                parsed_char_id = int(char_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid character_id."}), 400
            user = get_current_user()
            assert user is not None and user.id is not None
            char = CharacterRepository().get_by_id(parsed_char_id)
            if char is None or not char.is_editable_by_user(user.id, is_admin(), user.creator_tag):
                return jsonify({"error": "Character not found."}), 404
            req_portrait = (data.get("portrait_path") or "").strip()
            allowed_paths = {p for p in (char.primary_portrait_path, char.avatar_path, char.card_image_path) if p}
            if req_portrait:
                if req_portrait not in allowed_paths:
                    return jsonify({"error": "Portrait path does not belong to character."}), 403
                portrait_path = req_portrait
            else:
                portrait_path = char.primary_portrait_path
        elif data.get("portrait_path"):
            return jsonify({"error": "character_id is required when referencing an existing portrait_path."}), 400
    else:
        char_id = request.form.get("character_id")
        if char_id:
            try:
                parsed_char_id = int(char_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid character_id."}), 400
            user = get_current_user()
            assert user is not None and user.id is not None
            char = CharacterRepository().get_by_id(parsed_char_id)
            if char is None or not char.is_editable_by_user(user.id, is_admin(), user.creator_tag):
                return jsonify({"error": "Character not found."}), 404
            req_portrait = (request.form.get("portrait_path") or "").strip()
            allowed_paths = {p for p in (char.primary_portrait_path, char.avatar_path, char.card_image_path) if p}
            if req_portrait:
                if req_portrait not in allowed_paths:
                    return jsonify({"error": "Portrait path does not belong to character."}), 403
                portrait_path = req_portrait
            else:
                portrait_path = char.primary_portrait_path
        elif request.form.get("portrait_path"):
            return jsonify({"error": "character_id is required when referencing an existing portrait_path."}), 400

    if not portrait_path:
        return jsonify({"error": "Bitte lade zuerst ein Porträtbild hoch."}), 400

    resolved_path = storage.resolve_path(portrait_path)
    if not resolved_path.is_file():
        return jsonify({"error": "Kein gültiges Porträtbild zum Analysieren vorhanden."}), 400

    user = get_current_user()
    target_lang = (user.language if user and user.language else "en").strip().lower()[:2]
    from domain.translation.models import LANGUAGE_METADATA
    lang_label = LANGUAGE_METADATA.get(target_lang, {}).get("label", target_lang)

    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    from shared.i18n import t as core_t
    base_vision_prompt = core_t(settings.prompts.vision_persona_prompt, target_lang).strip()
    prompt = (
        f"{base_vision_prompt}\n"
        "Focus strictly on physical traits: face, eyes, hair, skin tone, clothing, and physique. "
        "Keep it concise and descriptive."
    )
    if target_lang != "en":
        prompt += f"\nRespond strictly in {lang_label} ({target_lang})."
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
