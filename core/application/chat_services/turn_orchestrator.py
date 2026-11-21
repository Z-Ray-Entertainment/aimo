from __future__ import annotations

from datetime import datetime, timezone
import threading

from application.chat_services.context_assembler import assemble_turn_context
from application.chat_services.post_stream_processor import (
    clean_streamed_reply,
    finalize_streamed_turn,
)
from application.chat_services.task_registry import (
    _BACKGROUND_TASKS,
    _TASKS_LOCK,
    BackgroundTurnTask,
)
from domain.chat.models import Message, MessageRole
from domain.chat.relationship import get_relationship_tier
from domain.chat.services import ChatService
from domain.worldinfo.models import EventCooldownState
from domain.worldinfo.services import WorldInfoService
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError
from shared.llm_activity import begin_interactive_llm, end_interactive_llm, touch_interactive_llm


def start_background_turn(
    session_id: int,
    user_text: str,
    user_language: str,
    uploaded_image_file=None,
    is_admin: bool = False,
    existing_user_msg: Message | None = None,
    target_ai_idx: int | None = None,
) -> tuple[BackgroundTurnTask, Message, dict | None]:
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
    worldinfo_events = wi_repo.list_events(worldinfo.id) if worldinfo and worldinfo.id is not None else []
    character_events = wi_repo.list_character_events(character.id) if character.id is not None else []
    all_session_events = worldinfo_events + character_events

    session_user = UserRepository().get_by_id(chat_session.user_id)
    session_user_tag = session_user.creator_tag if session_user else None
    can_view_event_counter = (
        is_admin
        or bool(worldinfo and worldinfo.is_editable_by_user(chat_session.user_id, is_admin, session_user_tag))
        or bool(character.is_editable_by_user(chat_session.user_id, is_admin, session_user_tag))
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
                    "worldinfo_event", triggered_event.id, "description", user_language, triggered_event.description
                )
                english_event_desc = trans_repo.get_localized_field(
                    "worldinfo_event", triggered_event.id, "description", "en", triggered_event.description
                )
                sys_msg = chat_service.create_event_trigger_message(
                    session=chat_session,
                    message_idx=chat_repo.get_next_message_idx(session_id),
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

    task = BackgroundTurnTask(
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
        w_settings_repo = SettingsRepository()
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
                    saved_user_msg.english_content = cleaned_user_text or image_alt_text
                    w_chat_repo.update_message(saved_user_msg)

                with task.condition:
                    task.image_alt_text = image_alt_text
                    task.image_analyzed = True
                    task.status = "thinking"
                    task.condition.notify_all()
            elif existing_user_msg is None:
                saved_user_msg.english_content = cleaned_user_text
                w_chat_repo.update_message(saved_user_msg)

            target_lang = (task.user_language or "en").strip().lower()[:2]
            ctx = assemble_turn_context(
                session=w_session,
                character=w_character,
                persona=w_persona,
                settings=settings,
                llm=llm,
                target_lang=target_lang,
                triggered_event=triggered_event,
            )
            if task.is_admin:
                task.assembled_prompt = ctx.admin_prompt

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
                    prompt=ctx.assembled_prompt,
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
                with task.condition:
                    task.error_message = llm.format_stream_error(exc, settings.tasks.roleplay_model)
                    task.status = "error"
                    task.condition.notify_all()
                return

            if task.is_aborted:
                with task.condition:
                    task.status = "aborted"
                    task.condition.notify_all()
                return

            english_reply = clean_streamed_reply(
                full_english_chunks, stop_sequences, w_character, w_persona
            )
            with task.condition:
                task.english_reply = english_reply
                task.generation_done = True
                task.status = "translating"
                task.condition.notify_all()

            payload = finalize_streamed_turn(
                task=task,
                session=w_session,
                character=w_character,
                settings=settings,
                llm=llm,
                available_locations=ctx.available_locations,
                english_reply=english_reply,
                cleaned_user_text=cleaned_user_text,
                target_ai_idx=target_ai_idx,
            )
            if payload is None:
                return

            with task.condition:
                task.result_payload = payload
                task.status = "completed"
                task.condition.notify_all()
        except Exception as exc:
            with task.condition:
                task.error_message = str(exc)
                task.status = "error"
                task.condition.notify_all()

    threading.Thread(target=_worker, daemon=True).start()

    triggered_event_dict = (
        {"id": triggered_event.id, "title": triggered_event.title}
        if triggered_event
        else None
    )
    return task, saved_user_msg, triggered_event_dict
