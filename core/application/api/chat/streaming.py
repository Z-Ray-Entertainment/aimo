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
    _PENDING_PROMPTS,
    _TASKS_LOCK,
    _USER_NOTIFICATIONS,
    _BackgroundTurnTask,
    _extract_active_tags,
    _get_authorized_session,
    _record_admin_prompt,
)

logger = logging.getLogger(__name__)

from application.api.chat.memories import _run_async_memory_extraction

def _start_background_turn(
    session_id: int,
    user_text: str,
    user_language: str,
    uploaded_image_file=None,
    is_admin: bool = False,
    existing_user_msg: Message | None = None,
    target_ai_idx: int | None = None,
) -> tuple[_BackgroundTurnTask, Message, dict | None]:
    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    chat_service = ChatService()
    wi_service = WorldInfoService()
    storage = FileStorage()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None:
        raise AimoError("Chat session not found.")

    character = char_repo.get_by_id(chat_session.character_id)
    if character is None or not character.is_visible_to_user(chat_session.user_id, is_admin):
        raise AimoError("Character not found.")

    persona = persona_repo.get_by_id(chat_session.persona_id)
    if persona is None:
        raise AimoError("Persona not found.")

    if existing_user_msg is not None:
        saved_user_msg = existing_user_msg
        image_path = saved_user_msg.image_path
        cleaned_user_text = saved_user_msg.localized_content or ""
    else:
        image_path = None
        if uploaded_image_file and uploaded_image_file.filename:
            image_path = storage.save_generated_image(
                uploaded_image_file.stream, uploaded_image_file.filename
            )

        chat_service.apply_time_decay(chat_session)
        chat_session.last_message_at = datetime.now(timezone.utc)
        chat_service.lock_persona(chat_session)

        cleaned_user_text = user_text.strip()
        next_idx = chat_repo.get_next_message_idx(session_id)
        user_msg = Message(
            id=None,
            session_id=session_id,
            message_idx=next_idx,
            role=MessageRole.USER,
            english_content=cleaned_user_text or "An uploaded image.",
            localized_content=cleaned_user_text,
            image_path=image_path,
            image_alt_text=None,
            created_at=datetime.now(timezone.utc),
        )
        saved_user_msg = chat_repo.add_message(user_msg)

    worldinfo = (
        wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if chat_session.active_worldinfo_id
        else None
    )
    worldinfo_events = (
        wi_repo.list_events(worldinfo.id)
        if worldinfo and worldinfo.id is not None
        else []
    )
    character_events = (
        wi_repo.list_character_events(character.id)
        if character and character.id is not None
        else []
    )
    all_session_events = worldinfo_events + character_events
    session_user = UserRepository().get_by_id(chat_session.user_id)
    session_user_tag = session_user.creator_tag if session_user else None
    can_view_event_counter = (
        is_admin
        or bool(worldinfo and worldinfo.is_editable_by_user(chat_session.user_id, is_admin, session_user_tag))
        or bool(character and character.is_editable_by_user(chat_session.user_id, is_admin, session_user_tag))
    )

    triggered_event = None
    saved_event_msg: Message | None = None
    if existing_user_msg is None and chat_session.events_enabled and all_session_events:
        cooldown_state = EventCooldownState(
            current_counter=chat_session.cooldown_counter,
            triggered_event_ids=set(chat_session.triggered_event_ids),
        )
        if wi_service.decrement_cooldown(cooldown_state):
            active_loc_id = chat_session.current_location_id if worldinfo else None
            current_rel_level = get_relationship_tier(chat_session.relationship_value).level
            triggered_event = wi_service.draw_event(
                worldinfo_events=all_session_events,
                current_location_id=active_loc_id,
                state=cooldown_state,
                current_relationship_level=current_rel_level,
            )
            if triggered_event and triggered_event.id is not None:
                trans_repo = TranslationRepository()
                localized_event_desc = trans_repo.get_localized_field(
                    "worldinfo_event",
                    triggered_event.id,
                    "description",
                    user_language,
                    triggered_event.description,
                )
                english_event_desc = trans_repo.get_localized_field(
                    "worldinfo_event",
                    triggered_event.id,
                    "description",
                    "en",
                    triggered_event.description,
                )
                event_msg_idx = chat_repo.get_next_message_idx(session_id)
                sys_msg = chat_service.create_event_trigger_message(
                    session=chat_session,
                    message_idx=event_msg_idx,
                    event_id=triggered_event.id,
                    event_title=triggered_event.title,
                    event_description=english_event_desc,
                    localized_description=localized_event_desc,
                    location_id=triggered_event.location_id,
                )
                saved_event_msg = chat_repo.add_message(sys_msg)
        chat_session.cooldown_counter = cooldown_state.current_counter
        chat_session.triggered_event_ids = cooldown_state.triggered_event_ids

    chat_repo.update_session(chat_session)

    task = _BackgroundTurnTask(
        session_id=session_id,
        user_id=chat_session.user_id,
        user_language=user_language,
        has_image=bool(image_path),
        user_message_idx=saved_user_msg.message_idx,
        is_admin=is_admin,
    )
    task.system_message = saved_event_msg
    task.can_view_event_counter = can_view_event_counter
    task.can_debug_relationship = is_admin or character.is_editable_by_user(
        chat_session.user_id, is_admin, session_user_tag
    )
    task.cooldown_counter = chat_session.cooldown_counter
    task.events_enabled = chat_session.events_enabled
    with _TASKS_LOCK:
        _BACKGROUND_TASKS[session_id] = task
    touch_interactive_llm()

    def _worker() -> None:
        begin_interactive_llm()
        try:
            _run_worker()
        finally:
            end_interactive_llm()

    def _run_worker() -> None:
        w_chat_repo = ChatRepository()
        w_char_repo = CharacterRepository()
        w_persona_repo = PersonaRepository()
        w_wi_repo = WorldInfoRepository()
        w_lb_repo = LorebookRepository()
        w_mem_repo = MemoryRepository()
        w_trans_repo = TranslationRepository()
        w_rel_repo = RelationshipRepository()
        w_settings_repo = SettingsRepository()

        w_char_service = CharacterService()
        w_wi_service = WorldInfoService()
        w_lb_service = LorebookService()
        w_chat_service = ChatService()
        w_mem_service = MemoryService()
        w_trans_service = TranslationService()
        w_prompt_builder = PromptBuilder()
        w_storage = FileStorage()

        try:
            if task.is_aborted:
                return

            w_session = w_chat_repo.get_session(session_id)
            if w_session is None:
                with task.condition:
                    task.error_message = "Session not found"
                    task.status = "error"
                    task.condition.notify_all()
                return

            w_character = w_char_repo.get_by_id(w_session.character_id)
            w_persona = w_persona_repo.get_by_id(w_session.persona_id)
            if w_character is None or w_persona is None:
                with task.condition:
                    task.error_message = "Character or Persona not found"
                    task.status = "error"
                    task.condition.notify_all()
                return

            settings = w_settings_repo.get_settings()
            llm = get_llm_provider(settings)

            image_alt_text: str | None = None
            if image_path:
                if existing_user_msg is not None and saved_user_msg.image_alt_text:
                    image_alt_text = saved_user_msg.image_alt_text
                else:
                    try:
                        resolved_img = w_storage.resolve_path(image_path)
                        image_alt_text = llm.analyze_image(
                            image_path=resolved_img,
                            prompt="Describe what is shown in this image concisely in English for a roleplay conversation.",
                            model=settings.tasks.vision_model,
                        ).strip()
                    except Exception:
                        image_alt_text = "An uploaded image."

                    saved_user_msg.image_alt_text = image_alt_text
                    saved_user_msg.english_content = cleaned_user_text or (image_alt_text or "")
                    w_chat_repo.update_message(saved_user_msg)

                with task.condition:
                    task.image_alt_text = image_alt_text
                    task.image_analyzed = True
                    task.status = "thinking"
                    task.condition.notify_all()
            else:
                if existing_user_msg is None:
                    saved_user_msg.english_content = cleaned_user_text
                    w_chat_repo.update_message(saved_user_msg)

            target_lang = (task.user_language or "en").strip().lower()[:2]

            if w_character.id is not None:
                w_character.description = w_trans_repo.get_localized_field(
                    "character", w_character.id, "description", target_lang, w_character.description
                )
                if getattr(w_character, "appearance", None):
                    w_character.appearance = w_trans_repo.get_localized_field(
                        "character", w_character.id, "appearance", target_lang, w_character.appearance
                    )
                raw_default_examples = (
                    "\n\n".join([
                        f"<START>\n{ex['trigger']}\n{ex['response']}" if isinstance(ex, dict) else str(ex)
                        for ex in w_character.dialogue_examples
                    ])
                    if isinstance(w_character.dialogue_examples, list)
                    else str(w_character.dialogue_examples or "")
                )
                localized_dialogue = w_trans_repo.get_localized_field(
                    "character",
                    w_character.id,
                    "dialogue_examples",
                    target_lang,
                    raw_default_examples,
                )
                if isinstance(localized_dialogue, str):
                    if "<START>" in localized_dialogue:
                        w_character.dialogue_examples = [
                            f"<START>\n{blk.strip()}"
                            for blk in localized_dialogue.split("<START>")
                            if blk.strip()
                        ]
                    else:
                        w_character.dialogue_examples = [
                            line.strip()
                            for line in localized_dialogue.splitlines()
                            if line.strip()
                        ]
                elif isinstance(localized_dialogue, list):
                    w_character.dialogue_examples = [
                        str(x).strip() for x in localized_dialogue if str(x).strip()
                    ]

            if w_persona.id is not None:
                w_persona.description = w_trans_repo.get_localized_field(
                    "persona", w_persona.id, "description", target_lang, w_persona.description
                )
                w_persona.appearance = w_trans_repo.get_localized_field(
                    "persona", w_persona.id, "appearance", target_lang, w_persona.appearance
                )

            w_worldinfo = (
                w_wi_repo.get_by_id(w_session.active_worldinfo_id)
                if w_session.active_worldinfo_id
                else None
            )
            available_locations = (
                [
                    loc for loc in w_wi_repo.list_locations(w_worldinfo.id)
                    if loc.character_id is None or loc.character_id == w_session.character_id
                ]
                if w_worldinfo and w_worldinfo.id is not None
                else []
            )
            for avail_loc in available_locations:
                if avail_loc.id is not None:
                    avail_loc.name = w_trans_repo.get_localized_field(
                        "worldinfo_location", avail_loc.id, "name", target_lang, avail_loc.name
                    )
            current_location = (
                w_wi_repo.get_location(w_session.current_location_id)
                if w_session.current_location_id
                else None
            )
            if current_location and current_location.id is not None:
                current_location.name = w_trans_repo.get_localized_field(
                    "worldinfo_location",
                    current_location.id,
                    "name",
                    target_lang,
                    current_location.name,
                )
                current_location.description = w_trans_repo.get_localized_field(
                    "worldinfo_location",
                    current_location.id,
                    "description",
                    target_lang,
                    current_location.description,
                )

            if triggered_event and triggered_event.id is not None:
                triggered_event.title = w_trans_repo.get_localized_field(
                    "worldinfo_event",
                    triggered_event.id,
                    "title",
                    target_lang,
                    triggered_event.title,
                )
                triggered_event.description = w_trans_repo.get_localized_field(
                    "worldinfo_event",
                    triggered_event.id,
                    "description",
                    target_lang,
                    triggered_event.description,
                )

            raw_recent = w_chat_repo.get_messages(session_id, limit=30)
            recent_messages = [
                m for m in raw_recent if m.role in (MessageRole.USER, MessageRole.CHARACTER)
            ][-10:]
            combined_context_text = " ".join(
                (m.localized_content or m.english_content or "") for m in recent_messages[-2:]
            )
            active_tags = _extract_active_tags(combined_context_text)
            latest_user_msg = next(
                (m for m in reversed(recent_messages) if m.role == MessageRole.USER),
                None,
            )
            latest_user_text = (
                (latest_user_msg.localized_content or latest_user_msg.english_content or "")
                if latest_user_msg is not None
                else ""
            )
            latest_user_tags = _extract_active_tags(latest_user_text)

            focus_analyzer = PythonFocusAnalyzer()
            scene_focus = focus_analyzer.analyze(
                recent_messages=recent_messages,
                active_tags=active_tags,
                has_triggered_event=(triggered_event is not None),
            )
            focus_keywords = focus_analyzer.get_focus_keywords(scene_focus)

            all_memories = w_mem_repo.list_for_session(session_id)
            matched_memories = w_mem_service.search_memories_by_tags(
                all_memories,
                active_tags,
                latest_tags=latest_user_tags,
                focus_keywords=focus_keywords,
            )

            effective_lb_ids = w_chat_service.get_effective_lorebook_ids(
                session=w_session,
                character_lorebook_ids=w_character.linked_lorebook_ids,
                worldinfo_lorebook_id=w_worldinfo.lorebook_id if w_worldinfo else None,
                character_world_conditions=getattr(w_character, "lorebook_world_conditions", {}) or {},
            )
            preferred_lb_ids: set[int] | None = None
            if scene_focus == SceneFocus.INTIMACY_BIO and w_character.linked_lorebook_ids:
                preferred_lb_ids = set(w_character.linked_lorebook_ids)
            elif scene_focus == SceneFocus.WORLD_EXPLORATION and w_worldinfo and w_worldinfo.lorebook_id:
                preferred_lb_ids = {w_worldinfo.lorebook_id}

            all_lorebook_entries = w_lb_repo.list_entries_for_lorebooks(effective_lb_ids)
            for lb_entry in all_lorebook_entries:
                if lb_entry.id is not None:
                    lb_entry.title = w_trans_repo.get_localized_field(
                        "lorebook_entry", lb_entry.id, "title", target_lang, lb_entry.title
                    )
                    lb_entry.content = w_trans_repo.get_localized_field(
                        "lorebook_entry", lb_entry.id, "content", target_lang, lb_entry.content
                    )
                    raw_tags = w_trans_repo.get_localized_field(
                        "lorebook_entry", lb_entry.id, "tags", target_lang, ""
                    )
                    if raw_tags:
                        lb_entry.tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            matched_lorebooks = w_lb_service.search_entries_by_tags(
                all_lorebook_entries,
                active_tags,
                latest_tags=latest_user_tags,
                focus_keywords=focus_keywords,
                preferred_lorebook_ids=preferred_lb_ids,
            )

            effective_num_ctx = settings.params.num_ctx
            if effective_num_ctx <= 0:
                effective_num_ctx = llm.get_model_context_length(settings.tasks.roleplay_model) or 4096

            raw_rp_prompt = settings.prompts.roleplay_prompt
            if is_default_prompt("roleplay_prompt", raw_rp_prompt):
                resolved_rp_prompt = get_default_prompt("roleplay_prompt", target_lang)
            else:
                resolved_rp_prompt = w_trans_repo.get_localized_field(
                    "system_prompt", 1, "roleplay_prompt", target_lang, raw_rp_prompt
                )

            assembled_prompt = w_prompt_builder.build_roleplay_prompt(
                roleplay_system_prompt=resolved_rp_prompt,
                character=w_character,
                persona=w_persona,
                worldinfo=w_worldinfo,
                current_location=current_location,
                triggered_event=triggered_event,
                recent_messages=recent_messages,
                matched_memories=matched_memories,
                matched_lorebooks=matched_lorebooks,
                available_locations=available_locations,
                relationship_value=w_session.relationship_value,
                relation_translations=None,
                scene_focus=scene_focus,
                effective_num_ctx=effective_num_ctx,
                thinking_enabled=bool(w_session.thinking_enabled),
                active_tags=active_tags,
                language=target_lang,
            )
            if task.is_admin:
                if w_prompt_builder.last_budget_report is not None:
                    task.assembled_prompt = (
                        f"{w_prompt_builder.last_budget_report.format_header()}\n\n{assembled_prompt}"
                    )
                else:
                    task.assembled_prompt = assembled_prompt

            with task.condition:
                task.status = "streaming"
                task.condition.notify_all()

            stop_sequences = [
                f"\n{w_persona.name}:",
                f"\n{w_persona.name} (Player):",
                f"\n[{w_persona.name}]:",
                "\n[USER_PERSONA]",
                "\n[RELATION]",
                "\n[CHAT_HISTORY]",
                "\n[DIALOGUE_EXAMPLES]",
                "\n[WORLD_INFO]",
            ]

            full_english_chunks: list[str] = []
            try:
                for token in llm.generate_stream(
                    prompt=assembled_prompt,
                    model=settings.tasks.roleplay_model,
                    params=settings.params,
                    stop=stop_sequences,
                    think=bool(w_session.thinking_enabled),
                ):
                    if task.is_aborted:
                        break
                    full_english_chunks.append(token)
                    with task.condition:
                        task.tokens.append({"token": token})
                        task.condition.notify_all()
            except Exception as exc:
                if task.is_aborted:
                    return
                user_friendly_err = llm.format_stream_error(exc, settings.tasks.roleplay_model)

                with task.condition:
                    task.error_message = user_friendly_err
                    task.status = "error"
                    task.condition.notify_all()
                return

            if task.is_aborted:
                with task.condition:
                    task.status = "aborted"
                    task.condition.notify_all()
                return

            raw_reply = "".join(full_english_chunks).strip()
            # Clean thinking tags from raw_reply before processing and translation
            cleaned_narrative = re.sub(
                r"<(?:think|thought|reasoning)>.*?</(?:think|thought|reasoning)>",
                "",
                raw_reply,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()
            if cleaned_narrative:
                raw_reply = cleaned_narrative

            for stop_seq in stop_sequences:
                if stop_seq.strip() and stop_seq in raw_reply:
                    raw_reply = raw_reply.split(stop_seq)[0].strip()

            english_reply = replace_roleplay_placeholders(
                raw_reply,
                w_character.name,
                w_persona.name,
                character_gender=w_character.gender.value,
                persona_gender=w_persona.gender.value,
            )
            with task.condition:
                task.english_reply = english_reply
                task.generation_done = True
                task.status = "translating"
                task.condition.notify_all()

            # 1. Emotionsanalyse nur durchführen, wenn der Charakter emotionale Sprites besitzt
            emotion_candidates = None
            if w_character.sprites:
                distinct_emotions = {sp.emotion for sp in w_character.sprites}
                if len(distinct_emotions) > 1 or (len(distinct_emotions) == 1 and Emotion.NEUTRAL not in distinct_emotions):
                    emotion_candidates = sorted(
                        {e.value for e in distinct_emotions} | {Emotion.NEUTRAL.value}
                    )

            # 2. Ortsanalyse nur durchführen, wenn eine WorldInfo mit alternativen Orten am Chat hängt
            other_locations = []
            loc_candidates = None
            if w_session.active_worldinfo_id is not None:
                locations = w_wi_repo.list_locations(w_session.active_worldinfo_id)
                other_locations = [
                    loc for loc in locations
                    if loc.id != w_session.current_location_id
                    and (loc.character_id is None or loc.character_id == w_session.character_id)
                ]
                for oloc in other_locations:
                    if oloc.id is not None:
                        oloc.name = w_trans_repo.get_localized_field(
                            "worldinfo_location", oloc.id, "name", target_lang, oloc.name
                        )
                if other_locations:
                    loc_candidates = ["stay_here"] + [loc.name for loc in other_locations]

            classification_model = (
                settings.tasks.classification_model
                if getattr(settings.tasks, "classification_model", None)
                else settings.tasks.roleplay_model
            )
            effective_cls_ctx = (
                settings.params.num_ctx
                if classification_model == settings.tasks.roleplay_model
                else 2048
            )

            detected_emotion_str = Emotion.NEUTRAL.value
            matched_loc_name = None
            raw_impact = RelationshipImpact.NEUTRAL.value
            current_tier_en = w_rel_repo.get_tier(w_session.relationship_value, language="en")
            try:
                detected_emotion_str, matched_loc_name, raw_impact = llm.classify_turn(
                    text=english_reply,
                    emotion_candidates=emotion_candidates,
                    location_candidates=loc_candidates,
                    model=classification_model,
                    user_text=cleaned_user_text,
                    character_name=w_character.name,
                    relationship_tier=current_tier_en.name,
                    evaluate_relationship=True,
                    num_ctx=effective_cls_ctx,
                )
            except Exception:
                detected_emotion_str = Emotion.NEUTRAL.value
                matched_loc_name = None
                raw_impact = RelationshipImpact.NEUTRAL.value

            detected_emotion = Emotion.resolve(detected_emotion_str)
            impact = RelationshipImpact.resolve(raw_impact)
            selected_sprite = w_char_service.select_sprite_for_emotion(w_character, detected_emotion)

            suggested_location = None
            if matched_loc_name and other_locations:
                for loc in other_locations:
                    if loc.name.lower() == matched_loc_name.strip().lower():
                        suggested_location = {
                            "id": loc.id,
                            "name": loc.name,
                            "background_image_path": loc.background_image_path,
                        }
                        break

            # Direct native-language chat: LLM already streamed in user_language
            localized_reply = english_reply

            if task.is_aborted:
                with task.condition:
                    task.status = "aborted"
                    task.condition.notify_all()
                return

            latest_session = w_chat_repo.get_session(session_id) or w_session
            applied_delta = w_chat_service.apply_relationship_impact(latest_session, impact)
            w_chat_repo.update_session(latest_session)

            ai_next_idx = target_ai_idx if target_ai_idx is not None else w_chat_repo.get_next_message_idx(session_id)
            ai_msg = Message(
                id=None,
                session_id=session_id,
                message_idx=ai_next_idx,
                role=MessageRole.CHARACTER,
                english_content=english_reply,
                localized_content=localized_reply,
                emotion_tag=detected_emotion.value,
                metadata={
                    "relationship_impact": impact.value,
                    "relationship_delta": applied_delta,
                },
                created_at=datetime.now(timezone.utc),
            )
            saved_ai_msg = w_chat_repo.add_message(ai_msg)
            if task.is_admin and task.assembled_prompt:
                _record_admin_prompt(session_id, saved_ai_msg.message_idx, task.assembled_prompt)

            _run_async_memory_extraction(session_id)

            tier = w_rel_repo.get_tier(latest_session.relationship_value, language=task.user_language)

            payload = {
                "notification_id": task.task_id,
                "message_id": saved_ai_msg.id,
                "message_idx": saved_ai_msg.message_idx,
                "english_content": english_reply,
                "localized_content": localized_reply,
                "emotion": detected_emotion.value,
                "sprite_path": selected_sprite.file_path,
                "relationship_value": latest_session.relationship_value,
                "relationship_tier_name": tier.name,
                "relationship_impact": impact.value,
                "suggested_location": suggested_location,
            }
            if task.can_view_event_counter:
                payload["cooldown_counter"] = latest_session.cooldown_counter
                payload["events_enabled"] = latest_session.events_enabled
            if task.can_debug_relationship:
                payload["relationship_delta"] = applied_delta
            if task.is_admin and task.assembled_prompt:
                payload["prompt"] = task.assembled_prompt

            with _TASKS_LOCK:
                user_notifs = _USER_NOTIFICATIONS.setdefault(w_session.user_id, [])
                user_notifs.append(
                    {
                        "id": task.task_id,
                        "session_id": session_id,
                        "session_title": latest_session.title,
                        "character_id": w_character.id,
                        "character_name": w_character.name,
                        "character_portrait": w_character.avatar_path or w_character.primary_portrait_path,
                        "message_id": saved_ai_msg.id,
                        "message_idx": saved_ai_msg.message_idx,
                        "localized_content": localized_reply,
                        "emotion": detected_emotion.value,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

            with task.condition:
                task.result_payload = payload
                task.status = "completed"
                task.condition.notify_all()
        except Exception as exc:
            with task.condition:
                task.error_message = str(exc)
                task.status = "error"
                task.condition.notify_all()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    triggered_event_dict = (
        {"id": triggered_event.id, "title": triggered_event.title}
        if triggered_event
        else None
    )
    return task, saved_user_msg, triggered_event_dict


def _stream_from_task(task: _BackgroundTurnTask):
    sent_tokens = 0
    sent_gen_done = False
    sent_image_analyzed = False
    sent_system_message = False

    # Emit system message immediately upon stream start if already present
    if task.system_message is not None and not sent_system_message:
        sent_system_message = True
        sys_msg_data = {
            "id": task.system_message.id,
            "session_id": task.system_message.session_id,
            "message_idx": task.system_message.message_idx,
            "role": task.system_message.role.value,
            "system_type": task.system_message.system_type,
            "english_content": task.system_message.english_content,
            "localized_content": task.system_message.localized_content,
            "metadata": task.system_message.metadata,
            "created_at": task.system_message.created_at.isoformat(),
        }
        yield f"event: system_message\ndata: {json.dumps(sys_msg_data)}\n\n"

    while True:
        with task.condition:
            while (
                sent_tokens >= len(task.tokens)
                and (sent_gen_done or not task.generation_done)
                and (sent_image_analyzed or not task.image_analyzed)
                and (sent_system_message or task.system_message is None)
                and task.status not in ("completed", "error", "aborted")
            ):
                task.condition.wait(timeout=15.0)

            emit_sys_msg = task.system_message is not None and not sent_system_message
            if emit_sys_msg:
                sent_system_message = True

            emit_image_analyzed = task.image_analyzed and not sent_image_analyzed
            if emit_image_analyzed:
                sent_image_analyzed = True
            image_alt_text = task.image_alt_text

            new_tokens = list(task.tokens[sent_tokens:])
            sent_tokens = len(task.tokens)
            emit_gen_done = task.generation_done and not sent_gen_done
            if emit_gen_done:
                sent_gen_done = True
            english_reply = task.english_reply
            current_status = task.status
            result_payload = task.result_payload
            error_message = task.error_message

        if emit_sys_msg and task.system_message is not None:
            sys_msg_data = {
                "id": task.system_message.id,
                "session_id": task.system_message.session_id,
                "message_idx": task.system_message.message_idx,
                "role": task.system_message.role.value,
                "system_type": task.system_message.system_type,
                "english_content": task.system_message.english_content,
                "localized_content": task.system_message.localized_content,
                "metadata": task.system_message.metadata,
                "created_at": task.system_message.created_at.isoformat(),
            }
            yield f"event: system_message\ndata: {json.dumps(sys_msg_data)}\n\n"

        if emit_image_analyzed:
            yield f"event: image_analyzed\ndata: {json.dumps({'image_alt_text': image_alt_text or '', 'user_message_idx': task.user_message_idx})}\n\n"

        for tok_data in new_tokens:
            yield f"event: token\ndata: {json.dumps(tok_data)}\n\n"

        if emit_gen_done:
            yield f"event: generation_done\ndata: {json.dumps({'english_content': english_reply})}\n\n"

        if current_status == "aborted" or task.is_aborted:
            task.delivered_via_stream = True
            yield f"event: aborted\ndata: {json.dumps({'error': error_message or 'Generation aborted by user'})}\n\n"
            break

        if current_status == "error":
            task.delivered_via_stream = True
            yield f"event: error\ndata: {json.dumps({'error': error_message or 'Generation error'})}\n\n"
            break

        if current_status == "completed" and result_payload is not None:
            task.delivered_via_stream = True
            yield f"event: message_complete\ndata: {json.dumps(result_payload)}\n\n"
            break


@api_chat_bp.route("/<int:session_id>/messages", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def post_message(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    if request.is_json:
        data = request.get_json(silent=True) or {}
        user_text = str(data.get("message", "")).strip()
        user_lang = str(data.get("language", "de")).strip()
        stream_now = bool(data.get("stream", True))
        uploaded_file = None
    else:
        user_text = str(request.form.get("message", "")).strip()
        user_lang = str(request.form.get("language", "de")).strip()
        stream_now = request.form.get("stream", "true").lower() == "true"
        uploaded_file = request.files.get("image")

    if not user_text and not uploaded_file:
        return jsonify({"error": "Message or image is required."}), 400

    try:
        task, user_msg, triggered_event = _start_background_turn(
            session_id=session_id,
            user_text=user_text,
            user_language=user_lang,
            uploaded_image_file=uploaded_file,
            is_admin=is_admin,
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    if not stream_now:
        sys_msg_dict = None
        if task.system_message is not None:
            sys_msg_dict = {
                "id": task.system_message.id,
                "session_id": task.system_message.session_id,
                "message_idx": task.system_message.message_idx,
                "role": task.system_message.role.value,
                "system_type": task.system_message.system_type,
                "english_content": task.system_message.english_content,
                "localized_content": task.system_message.localized_content,
                "metadata": task.system_message.metadata,
                "created_at": task.system_message.created_at.isoformat(),
            }
        return jsonify(
            {
                "status": "ready_for_stream",
                "task_id": task.task_id,
                "has_image": task.has_image,
                "user_message": {
                    "id": user_msg.id,
                    "message_idx": user_msg.message_idx,
                    "localized_content": user_msg.localized_content,
                    "image_path": user_msg.image_path,
                    "image_alt_text": user_msg.image_alt_text,
                },
                "triggered_event": triggered_event,
                "system_message": sys_msg_dict,
                "cooldown_counter": task.cooldown_counter if task.can_view_event_counter else None,
                "events_enabled": task.events_enabled,
            }
        )

    return Response(
        stream_with_context(_stream_from_task(task)),
        content_type="text/event-stream; charset=utf-8",
    )


@api_chat_bp.route("/<int:session_id>/stream", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def stream_session_response(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    user_lang = request.args.get("language", "de")
    msg_text = request.args.get("message", "").strip()

    if msg_text:
        try:
            task, _, _ = _start_background_turn(
                session_id=session_id,
                user_text=msg_text,
                user_language=user_lang,
                is_admin=is_admin,
            )
        except AimoError as exc:
            return jsonify({"error": str(exc)}), 400
    else:
        with _TASKS_LOCK:
            task = _BACKGROUND_TASKS.get(session_id)
        if task is None or (task.status in ("completed", "error") and task.delivered_via_stream):
            return jsonify({"error": "No pending message for stream."}), 400

    return Response(
        stream_with_context(_stream_from_task(task)),
        content_type="text/event-stream; charset=utf-8",
    )


@api_chat_bp.route("/<int:session_id>/status", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def get_session_generation_status(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    with _TASKS_LOCK:
        task = _BACKGROUND_TASKS.get(session_id)

    if task is None:
        return jsonify({"active": False, "status": "idle"})

    with task.condition:
        is_active = task.status in ("analyzing_image", "thinking", "streaming", "translating")
        return jsonify(
            {
                "active": is_active,
                "task_id": task.task_id,
                "status": task.status,
                "has_image": task.has_image,
            }
        )


@api_chat_bp.route("/<int:session_id>/abort", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def abort_generation(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    with _TASKS_LOCK:
        task = _BACKGROUND_TASKS.get(session_id)

    if task is None:
        return jsonify({"aborted": False, "message": "No active turn."})

    with task.condition:
        if task.status in ("analyzing_image", "thinking", "streaming", "translating"):
            task.is_aborted = True
            task.status = "aborted"
            task.error_message = "Generation aborted by user"
            task.condition.notify_all()
            return jsonify({"aborted": True})

    return jsonify({"aborted": False, "status": task.status if task else "idle"})


