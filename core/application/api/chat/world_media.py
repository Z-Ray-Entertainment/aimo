from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import threading
import uuid

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.auth import get_current_user, has_perm, require_permission
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.chat.focus_analyzer import PythonFocusAnalyzer, SceneFocus
from domain.chat.models import ChatSession, Message, MessageRole
from domain.chat.prompt_builder import PromptBuilder
from domain.chat.relationship import RelationshipImpact, get_relationship_tier
from domain.chat.services import ChatService
from domain.lorebooks.services import LorebookService
from domain.memories.services import MemoryService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters, get_default_prompt, is_default_prompt
from domain.translation.services import TranslationService
from domain.worldinfo.models import EventCooldownState
from domain.worldinfo.services import WorldInfoService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError
from shared.llm_activity import (
    begin_interactive_llm,
    end_interactive_llm,
    interactive_llm_guard,
    is_interactive_llm_busy,
    touch_interactive_llm,
)
from shared.utils import filter_stopwords, parse_tags, replace_roleplay_placeholders

from application.api.chat import api_chat_bp
from application.api.chat.shared import (
    _ACTIVE_IMAGE_TASKS,
    _ADMIN_PROMPT_CACHE,
    _BACKGROUND_TASKS,
    _TASKS_LOCK,
    _USER_NOTIFICATIONS,
    _BackgroundTurnTask,
    _extract_active_tags,
    _get_authorized_session,
    _record_admin_prompt,
)

logger = logging.getLogger(__name__)

@api_chat_bp.route("/<int:session_id>/recalculate-relationship", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def recalculate_relationship(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    user_lang = str(data.get("language", "de")).strip()

    char_repo = CharacterRepository()
    character = char_repo.get_by_id(chat_session.character_id)
    if character is None:
        return jsonify({"error": "Character not found."}), 404

    chat_repo = ChatRepository()
    rel_repo = RelationshipRepository()
    settings_repo = SettingsRepository()
    chat_service = ChatService()

    settings = settings_repo.get_settings()
    classification_model = (
        settings.tasks.classification_model
        if getattr(settings.tasks, "classification_model", None)
        else settings.tasks.roleplay_model
    )
    llm = get_llm_provider(settings)

    previous_value = chat_session.relationship_value
    initial_value = chat_service.reset_relationship(chat_session, character)

    messages = chat_repo.get_messages(session_id, limit=None)
    pending_user_msg: Message | None = None
    turns: list[tuple[Message, str, str]] = []
    for msg in messages:
        if msg.role == MessageRole.USER:
            pending_user_msg = msg
        elif msg.role == MessageRole.CHARACTER and msg.message_idx > 0:
            user_text = (
                (pending_user_msg.localized_content or pending_user_msg.english_content)
                if pending_user_msg is not None
                else ""
            )
            ai_text = msg.english_content or msg.localized_content
            turns.append((msg, user_text, ai_text))
            pending_user_msg = None

    effective_cls_ctx = (
        settings.params.num_ctx
        if classification_model == settings.tasks.roleplay_model
        else 2048
    )

    def _classify_single_turn(turn: tuple[Message, str, str]) -> str:
        _, u_text, a_text = turn
        try:
            _, _, impact_str = llm.classify_turn(
                text=a_text,
                emotion_candidates=None,
                location_candidates=None,
                model=classification_model,
                user_text=u_text,
                character_name=character.name,
                evaluate_relationship=True,
                num_ctx=effective_cls_ctx,
            )
            return impact_str
        except Exception:
            return RelationshipImpact.NEUTRAL.value

    if llm.is_cloud_provider() and len(turns) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as executor:
            raw_impacts = list(executor.map(_classify_single_turn, turns))
    else:
        raw_impacts = [_classify_single_turn(t) for t in turns]

    evaluated_turns = 0
    turn_results: list[dict[str, object]] = []
    for (msg, _, _), raw_impact in zip(turns, raw_impacts):
        impact = RelationshipImpact.resolve(raw_impact)
        applied_delta = chat_service.apply_relationship_impact(
            chat_session, impact, update_timestamp=False
        )

        msg.metadata = dict(msg.metadata or {})
        msg.metadata["relationship_impact"] = impact.value
        msg.metadata["relationship_delta"] = applied_delta
        chat_repo.update_message(msg)

        evaluated_turns += 1
        turn_results.append(
            {
                "message_idx": msg.message_idx,
                "impact": impact.value,
                "delta": applied_delta,
            }
        )

    chat_repo.update_session(chat_session)
    tier = rel_repo.get_tier(chat_session.relationship_value, language=user_lang)
    net_delta = chat_session.relationship_value - previous_value
    recalc_delta = chat_session.relationship_value - initial_value
    net_impact = "positive" if net_delta > 0 else ("negative" if net_delta < 0 else "neutral")

    return jsonify(
        {
            "relationship_value": chat_session.relationship_value,
            "relationship_tier_name": tier.name,
            "relationship_impact": net_impact,
            "relationship_delta": round(recalc_delta, 4),
            "evaluated_turns": evaluated_turns,
            "turn_results": turn_results,
        }
    )


@api_chat_bp.route("/<int:session_id>/switch-location", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def switch_location(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Chat session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    raw_loc_id = data.get("location_id")

    chat_repo = ChatRepository()
    wi_repo = WorldInfoRepository()
    chat_service = ChatService()
    prev_loc_id = chat_session.current_location_id

    if raw_loc_id in (None, "", "world", 0, "0"):
        if chat_session.active_worldinfo_id is None:
            return jsonify({"error": "No active WorldInfo in this chat session."}), 400
        wi = wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if wi is None or not wi.is_visible_to_user(user.id, is_admin):
            return jsonify({"error": "WorldInfo not found."}), 404

        target_lang = getattr(user, "language", "en") or "en"
        world_name = (
            TranslationRepository().get_localized_field("worldinfo", wi.id, "name", target_lang, wi.name)
            if wi.id is not None
            else wi.name
        )

        chat_service.switch_location(chat_session, None)
        next_idx = chat_repo.get_next_message_idx(session_id)
        sys_msg = chat_service.create_location_change_message(
            session=chat_session,
            message_idx=next_idx,
            location_id=None,
            location_name=world_name,
            location_description=None,
            background_image_path=wi.backdrop_image_path,
            from_location_id=prev_loc_id,
        )
        saved_sys_msg = chat_repo.add_message(sys_msg)
        chat_repo.update_session(chat_session)

        return jsonify(
            {
                "status": "switched",
                "location": None,
                "worldinfo": {
                    "id": wi.id,
                    "name": world_name,
                    "backdrop_image_path": wi.backdrop_image_path,
                },
                "worldinfo_backdrop_path": wi.backdrop_image_path,
                "ui_notice": saved_sys_msg.localized_content,
                "system_message": {
                    "id": saved_sys_msg.id,
                    "session_id": saved_sys_msg.session_id,
                    "message_idx": saved_sys_msg.message_idx,
                    "role": saved_sys_msg.role.value,
                    "system_type": saved_sys_msg.system_type,
                    "english_content": saved_sys_msg.english_content,
                    "localized_content": saved_sys_msg.localized_content,
                    "metadata": saved_sys_msg.metadata,
                    "created_at": saved_sys_msg.created_at.isoformat(),
                },
            }
        )

    try:
        location_id = int(raw_loc_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid location_id."}), 400

    if chat_session.active_worldinfo_id is None:
        return jsonify({"error": "No active world is selected for this chat session."}), 400

    location = wi_repo.get_location(location_id)
    if location is None or location.worldinfo_id != chat_session.active_worldinfo_id:
        return jsonify({"error": "Location not found."}), 404

    wi = wi_repo.get_by_id(location.worldinfo_id)
    if wi is None or not wi.is_visible_to_user(user.id, is_admin):
        return jsonify({"error": "Location not found."}), 404

    if location.character_id is not None and location.character_id != chat_session.character_id:
        return jsonify({"error": "Dieser Ort ist an einen anderen Charakter gebunden und kann nicht betreten werden."}), 403

    chat_service.switch_location(chat_session, location.id)
    next_idx = chat_repo.get_next_message_idx(session_id)
    sys_msg = chat_service.create_location_change_message(
        session=chat_session,
        message_idx=next_idx,
        location_id=location.id,
        location_name=location.name,
        location_description=location.description,
        background_image_path=location.background_image_path,
        from_location_id=prev_loc_id,
    )
    saved_sys_msg = chat_repo.add_message(sys_msg)
    chat_repo.update_session(chat_session)

    return jsonify(
        {
            "status": "switched",
            "location": {
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "background_image_path": location.background_image_path,
            },
            "worldinfo_backdrop_path": wi.backdrop_image_path if wi else None,
            "ui_notice": saved_sys_msg.localized_content,
            "system_message": {
                "id": saved_sys_msg.id,
                "session_id": saved_sys_msg.session_id,
                "message_idx": saved_sys_msg.message_idx,
                "role": saved_sys_msg.role.value,
                "system_type": saved_sys_msg.system_type,
                "english_content": saved_sys_msg.english_content,
                "localized_content": saved_sys_msg.localized_content,
                "metadata": saved_sys_msg.metadata,
                "created_at": saved_sys_msg.created_at.isoformat(),
            },
        }
    )


@api_chat_bp.route("/<int:session_id>/generate-image", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def generate_scene_image(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    settings_repo = SettingsRepository()
    storage = FileStorage()

    character = char_repo.get_by_id(chat_session.character_id)
    persona = persona_repo.get_by_id(chat_session.persona_id)
    if character is None or persona is None:
        return jsonify({"error": "Character or Persona not found."}), 404

    trans_repo = TranslationRepository()
    if character.id is not None:
        character.description = trans_repo.get_localized_field(
            "character", character.id, "description", "en", character.description
        )
    if persona.id is not None:
        persona.description = trans_repo.get_localized_field(
            "persona", persona.id, "description", "en", persona.description
        )
        persona.appearance = trans_repo.get_localized_field(
            "persona", persona.id, "appearance", "en", persona.appearance
        )

    settings = settings_repo.get_settings()
    img_gen = get_image_gen_provider(settings)
    if not type(img_gen).is_enabled():
        return jsonify({"error": "Bildgenerierung ist deaktiviert."}), 400
    llm = get_llm_provider(settings)

    recent_msgs = [
        m
        for m in chat_repo.get_messages(session_id, limit=12)
        if m.role in (MessageRole.USER, MessageRole.CHARACTER)
    ][-4:]
    scene_text = "\n".join(f"{m.role.value}: {m.effective_text}" for m in recent_msgs)
    location_desc = "Neutral background"
    ref_images: list[Path] = []

    try:
        char_portrait = storage.resolve_path(character.primary_portrait_path)
        if char_portrait.is_file():
            ref_images.append(char_portrait)
    except Exception:
        pass

    try:
        pers_portrait = storage.resolve_path(persona.portrait_path)
        if pers_portrait.is_file():
            ref_images.append(pers_portrait)
    except Exception:
        pass

    if chat_session.active_worldinfo_id:
        loc = wi_repo.get_location(chat_session.current_location_id) if chat_session.current_location_id else None
        ref_bg_rel: str | None = None
        if loc:
            location_desc = f"{loc.name}: {loc.description}"
            ref_bg_rel = loc.background_image_path
        if not ref_bg_rel:
            active_wi = wi_repo.get_by_id(chat_session.active_worldinfo_id)
            if active_wi and active_wi.backdrop_image_path:
                ref_bg_rel = active_wi.backdrop_image_path
        if ref_bg_rel:
            try:
                bg_path = storage.resolve_path(ref_bg_rel)
                if bg_path.is_file():
                    ref_images.append(bg_path)
            except Exception:
                pass

    diffuser_instruction = img_gen.build_scene_prompt_instruction(
        diffuser_prompt=settings.prompts.diffuser_prompt,
        character_summary=f"{character.name} ({getattr(character, 'appearance', '') or character.description})",
        persona_summary=persona.appearance or persona.description,
        location_desc=location_desc,
        scene_text=scene_text,
    )

    try:
        with interactive_llm_guard():
            sd_prompt = llm.generate(
                prompt=diffuser_instruction,
                model=settings.tasks.assistant_model,
                params=ModelParameters(num_ctx=4096, temperature=0.5, top_p=0.9, repeat_penalty=1.05),
                think=False,
            ).strip()
        sd_prompt = re.sub(
            r"<(?:think|thought|reasoning)>.*?</(?:think|thought|reasoning)>",
            "",
            sd_prompt,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()
    except Exception:
        sd_prompt = f"{character.name}, {location_desc}, high quality roleplay scene"

    task_id = uuid.uuid4().hex
    _ACTIVE_IMAGE_TASKS[session_id] = task_id
    try:
        output_file = storage.allocate_generated_path("scene.png")
        generated_path = img_gen.generate_image(
            prompt=sd_prompt,
            reference_images=ref_images,
            negative_prompt="lowres, blurry, bad anatomy, text, watermark",
            output_path=output_file,
        )
        if _ACTIVE_IMAGE_TASKS.get(session_id) != task_id:
            try:
                generated_path.unlink(missing_ok=True)
            except OSError:
                pass
            return jsonify({"status": "cancelled", "session_id": session_id})
        rel_path = storage.to_relative_path(generated_path)
        return jsonify(
            {
                "status": "completed",
                "image_path": rel_path,
                "prompt": sd_prompt,
            }
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        if _ACTIVE_IMAGE_TASKS.get(session_id) == task_id:
            _ACTIVE_IMAGE_TASKS.pop(session_id, None)


@api_chat_bp.route("/<int:session_id>/cancel-image", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def cancel_image(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    task_id = _ACTIVE_IMAGE_TASKS.pop(session_id, "current")
    settings = SettingsRepository().get_settings()
    img_gen = get_image_gen_provider(settings)
    try:
        img_gen.cancel_generation(task_id)
    except AimoError:
        pass
    return jsonify({"status": "cancelled", "session_id": session_id})
