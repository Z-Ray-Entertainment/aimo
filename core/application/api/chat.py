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

api_chat_bp = Blueprint("api_chat", __name__, url_prefix="/api/chat")
logger = logging.getLogger(__name__)

_ACTIVE_IMAGE_TASKS: dict[int, str] = {}
_PENDING_PROMPTS: dict[int, dict] = {}


class _BackgroundTurnTask:
    def __init__(
        self,
        session_id: int,
        user_id: int,
        user_language: str = "de",
        has_image: bool = False,
        user_message_idx: int = 0,
        is_admin: bool = False,
    ) -> None:
        self.task_id: str = uuid.uuid4().hex
        self.session_id: int = session_id
        self.user_id: int = user_id
        self.user_language: str = user_language
        self.has_image: bool = has_image
        self.user_message_idx: int = user_message_idx
        self.is_admin: bool = is_admin
        self.system_message: Message | None = None
        self.can_view_event_counter: bool = False
        self.cooldown_counter: int | None = None
        self.events_enabled: bool = True
        self.assembled_prompt: str | None = None
        self.image_analyzed: bool = False
        self.image_alt_text: str | None = None
        self.condition: threading.Condition = threading.Condition()
        self.status: str = "analyzing_image" if has_image else "thinking"
        self.tokens: list[dict] = []
        self.english_reply: str = ""
        self.generation_done: bool = False
        self.result_payload: dict | None = None
        self.error_message: str | None = None
        self.delivered_via_stream: bool = False
        self.is_aborted: bool = False


_TASKS_LOCK = threading.Lock()
_BACKGROUND_TASKS: dict[int, _BackgroundTurnTask] = {}
_USER_NOTIFICATIONS: dict[int, list[dict]] = {}
_ADMIN_PROMPT_CACHE: dict[tuple[int, int], str] = {}
_ADMIN_PROMPT_MAX_ENTRIES: int = 150


def has_active_chat_tasks() -> bool:
    if is_interactive_llm_busy():
        return True
    with _TASKS_LOCK:
        return any(
            t.status in ("analyzing_image", "thinking", "streaming", "translating")
            and not t.is_aborted
            for t in _BACKGROUND_TASKS.values()
        )


def _record_admin_prompt(session_id: int, message_idx: int, prompt: str) -> None:
    with _TASKS_LOCK:
        if len(_ADMIN_PROMPT_CACHE) >= _ADMIN_PROMPT_MAX_ENTRIES:
            oldest_key = next(iter(_ADMIN_PROMPT_CACHE))
            _ADMIN_PROMPT_CACHE.pop(oldest_key, None)
        _ADMIN_PROMPT_CACHE[(session_id, message_idx)] = prompt


def _extract_active_tags(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9äöüÄÖÜß_-]{3,}", text.lower())
    clean_words = filter_stopwords(words)
    return parse_tags(clean_words)


def _run_async_memory_extraction(session_id: int) -> None:
    def _worker() -> None:
        try:
            chat_repo = ChatRepository()
            mem_repo = MemoryRepository()
            settings_repo = SettingsRepository()
            mem_service = MemoryService()

            chat_session = chat_repo.get_session(session_id)
            if chat_session is None:
                return

            all_messages = chat_repo.get_messages(session_id, limit=None)
            narrative_msgs = mem_service.filter_narrative_messages(all_messages)
            existing_memories = mem_repo.list_for_session(session_id)
            last_mem_idx = max((m.message_idx for m in existing_memories), default=0)
            unsummarized = [m for m in narrative_msgs if m.message_idx > last_mem_idx]

            if not mem_service.should_generate_memory(len(unsummarized)):
                return

            chunk = unsummarized[:10]
            target_idx = chunk[-1].message_idx
            settings = settings_repo.get_settings()
            llm = get_llm_provider(settings)

            session_user = UserRepository().get_by_id(chat_session.user_id)
            user_lang = (session_user.language if session_user and session_user.language else "en")[:2].lower()
            raw_mem_prompt = settings.prompts.memory_prompt
            if is_default_prompt("memory_prompt", raw_mem_prompt):
                resolved_mem_prompt = get_default_prompt("memory_prompt", user_lang)
            else:
                resolved_mem_prompt = TranslationRepository().get_localized_field(
                    "system_prompt", 1, "memory_prompt", user_lang, raw_mem_prompt
                )

            msg_dicts = [
                {"role": m.role.value, "content": m.localized_content or m.english_content or ""}
                for m in chunk
            ]
            with interactive_llm_guard():
                title, tags, summary, new_chat_title = mem_service.extract_memory_and_title(
                    last_10_messages=msg_dicts,
                    memory_prompt=resolved_mem_prompt,
                    llm_provider=llm,
                    model=settings.tasks.memory_model,
                    params=settings.params,
                )
            memory = mem_service.create_memory(
                chat_session_id=session_id,
                message_idx=target_idx,
                title=title,
                tags=tags,
                summary=summary,
            )
            mem_repo.add_memory(memory)

            if new_chat_title:
                chat_session.title = new_chat_title
                chat_repo.update_session(chat_session)
        except Exception as exc:
            logger.exception("Background memory generation failed for session %s: %s", session_id, exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _get_authorized_session(session_id: int, user) -> tuple[ChatSession | None, bool]:
    if user is None or user.id is None:
        return None, False
    chat_repo = ChatRepository()
    chat_session = chat_repo.get_session(session_id)
    if chat_session is None:
        return None, False
    is_admin = bool(user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS))
    if chat_session.user_id != user.id and not is_admin:
        return None, False
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(chat_session.character_id)
    if character is None or not character.is_visible_to_user(user.id, is_admin):
        return None, False
    return chat_session, is_admin


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

            recent_messages = w_chat_repo.get_messages(session_id, limit=10)
            combined_context_text = " ".join(
                (m.localized_content or m.english_content or "") for m in recent_messages[-2:]
            )
            active_tags = _extract_active_tags(combined_context_text)
            latest_user_text = (
                (recent_messages[-1].localized_content or recent_messages[-1].english_content or "")
                if recent_messages
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
                    emotion_candidates = [
                        e.value
                        for e in Emotion
                        if e.name not in ("EMBERASSED", "RELIFE", "SUPRISE")
                    ]

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


def _revert_relationship_for_messages(
    chat_service: ChatService,
    chat_session: ChatSession,
    messages: list[Message],
) -> bool:
    reverted = False
    for msg in messages:
        if msg.role != MessageRole.CHARACTER:
            continue
        raw_delta = msg.metadata.get("relationship_delta") if msg.metadata else None
        if isinstance(raw_delta, (int, float)) and not isinstance(raw_delta, bool):
            chat_service.revert_relationship_delta(chat_session, float(raw_delta))
            reverted = True
    return reverted


@api_chat_bp.route("/<int:session_id>/regenerate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def regenerate_turn(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    user_lang = str(data.get("language", "de")).strip()

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()

    all_messages = chat_repo.get_messages(session_id, limit=None)
    narrative_msgs = [
        m for m in all_messages if m.role in (MessageRole.USER, MessageRole.CHARACTER)
    ]
    if not narrative_msgs:
        return jsonify({"error": "Keine Nachrichten zum Neu-Generieren vorhanden."}), 400

    last_msg = narrative_msgs[-1]
    deleted_msg_idx = None
    target_ai_idx = None

    if last_msg.role == MessageRole.CHARACTER:
        if last_msg.message_idx == 0:
            return jsonify({"error": "Die Begrüßung der KI kann nicht neu generiert werden."}), 400

        if _revert_relationship_for_messages(chat_service, chat_session, [last_msg]):
            chat_repo.update_session(chat_session)

        if last_msg.id is not None:
            chat_repo.delete_single_message(last_msg.id)
        else:
            chat_repo.delete_message_by_idx(session_id, last_msg.message_idx)
        mem_repo.delete_after_idx(session_id, last_msg.message_idx - 1)
        deleted_msg_idx = last_msg.message_idx
        target_ai_idx = last_msg.message_idx

        updated_messages = [m for m in all_messages if m.id != last_msg.id]
        user_msgs = [m for m in updated_messages if m.role == MessageRole.USER]
        if not user_msgs:
            return jsonify({"error": "Keine Spielernachricht zum Neu-Generieren gefunden."}), 400
        target_user_msg = user_msgs[-1]

    elif last_msg.role == MessageRole.USER:
        target_user_msg = last_msg
        target_ai_idx = None
    else:
        return jsonify({"error": "Ungültiger Rollenstatus der letzten Nachricht."}), 400

    try:
        task, _, triggered_event = _start_background_turn(
            session_id=session_id,
            user_text=target_user_msg.localized_content or "",
            user_language=user_lang,
            is_admin=is_admin,
            existing_user_msg=target_user_msg,
            target_ai_idx=target_ai_idx,
        )
        return jsonify({
            "task_id": task.task_id,
            "session_id": session_id,
            "deleted_message_idx": deleted_msg_idx,
            "user_message_idx": target_user_msg.message_idx,
            "triggered_event": triggered_event,
        }), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>/prompt", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def get_message_prompt(session_id: int, message_idx: int):
    with _TASKS_LOCK:
        prompt = _ADMIN_PROMPT_CACHE.get((session_id, message_idx))
    if prompt is None:
        return jsonify({
            "error": "Prompt not available in memory.",
            "prompt": None,
        }), 404
    return jsonify({
        "session_id": session_id,
        "message_idx": message_idx,
        "prompt": prompt,
    })


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
    chat_service.reset_relationship(chat_session, character)

    messages = chat_repo.get_messages(session_id, limit=None)
    pending_user_msg: Message | None = None
    evaluated_turns = 0

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
            current_tier_en = rel_repo.get_tier(chat_session.relationship_value, language="en")

            try:
                _, _, raw_impact = llm.classify_turn(
                    text=ai_text,
                    emotion_candidates=None,
                    location_candidates=None,
                    model=classification_model,
                    user_text=user_text,
                    character_name=character.name,
                    relationship_tier=current_tier_en.name,
                    evaluate_relationship=True,
                )
            except Exception:
                raw_impact = RelationshipImpact.NEUTRAL.value

            impact = RelationshipImpact.resolve(raw_impact)
            applied_delta = chat_service.apply_relationship_impact(
                chat_session, impact, update_timestamp=False
            )

            msg.metadata = dict(msg.metadata or {})
            msg.metadata["relationship_impact"] = impact.value
            msg.metadata["relationship_delta"] = applied_delta
            chat_repo.update_message(msg)

            pending_user_msg = None
            evaluated_turns += 1

    chat_repo.update_session(chat_session)
    tier = rel_repo.get_tier(chat_session.relationship_value, language=user_lang)
    net_delta = chat_session.relationship_value - previous_value
    net_impact = "positive" if net_delta > 0 else ("negative" if net_delta < 0 else "neutral")

    return jsonify(
        {
            "relationship_value": chat_session.relationship_value,
            "relationship_tier_name": tier.name,
            "relationship_impact": net_impact,
            "evaluated_turns": evaluated_turns,
        }
    )


@api_chat_bp.route("/notifications", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def poll_chat_notifications():
    user = get_current_user()
    assert user is not None and user.id is not None

    raw_active = request.args.get("active_session_id", "").strip()
    active_session_id = int(raw_active) if raw_active.isdigit() else None

    to_deliver: list[dict] = []
    with _TASKS_LOCK:
        notifs = _USER_NOTIFICATIONS.get(user.id, [])
        remaining: list[dict] = []
        for item in notifs:
            if active_session_id is not None and item["session_id"] == active_session_id:
                continue
            to_deliver.append(item)
        _USER_NOTIFICATIONS[user.id] = remaining

    return jsonify({"notifications": to_deliver})


@api_chat_bp.route("/notifications/<string:notification_id>/ack", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def ack_chat_notification(notification_id: str):
    user = get_current_user()
    assert user is not None and user.id is not None

    with _TASKS_LOCK:
        notifs = _USER_NOTIFICATIONS.get(user.id, [])
        _USER_NOTIFICATIONS[user.id] = [
            item for item in notifs if item.get("id") != notification_id
        ]

    return jsonify({"status": "acknowledged"})


@api_chat_bp.route("/<int:session_id>/switch-location", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def switch_location(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Chat session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    location_id = int(data.get("location_id", 0))

    chat_repo = ChatRepository()
    wi_repo = WorldInfoRepository()

    location = wi_repo.get_location(location_id)
    if location is None:
        return jsonify({"error": "Location not found."}), 404

    wi = wi_repo.get_by_id(location.worldinfo_id)
    if wi and not wi.is_visible_to_user(user.id, is_admin):
        return jsonify({"error": "Location not found."}), 404

    if location.character_id is not None and location.character_id != chat_session.character_id:
        return jsonify({"error": "Dieser Ort ist an einen anderen Charakter gebunden und kann nicht betreten werden."}), 403

    chat_service = ChatService()
    chat_service.switch_location(chat_session, location.id)
    next_idx = chat_repo.get_next_message_idx(session_id)
    sys_msg = chat_service.create_location_change_message(
        session=chat_session,
        message_idx=next_idx,
        location_id=location.id,
        location_name=location.name,
        location_description=location.description,
        background_image_path=location.background_image_path,
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

    recent_msgs = chat_repo.get_messages(session_id, limit=4)
    scene_text = "\n".join(f"{m.role.value}: {m.english_content}" for m in recent_msgs)
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

    if chat_session.active_worldinfo_id and chat_session.current_location_id:
        loc = wi_repo.get_location(chat_session.current_location_id)
        if loc:
            location_desc = f"{loc.name}: {loc.description}"
            if loc.background_image_path:
                try:
                    bg_path = storage.resolve_path(loc.background_image_path)
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


@api_chat_bp.route("/<int:session_id>/fork", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def fork_chat_session(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    orig_session, _ = _get_authorized_session(session_id, user)
    if orig_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    fork_point_idx = int(data.get("fork_point_idx", 0))

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()
    mem_service = MemoryService()

    all_messages = chat_repo.get_messages(session_id, limit=None)
    forked_session, filtered_messages = chat_service.fork_session(
        session=orig_session,
        messages=all_messages,
        fork_point_idx=fork_point_idx,
    )
    forked_session.user_id = user.id
    saved_fork = chat_repo.create_session(forked_session)
    assert saved_fork.id is not None

    for msg in filtered_messages:
        msg.session_id = saved_fork.id
        chat_repo.add_message(msg)

    orig_memories = mem_repo.list_for_session(session_id)
    valid_memories = mem_service.filter_memories_for_fork(orig_memories, fork_point_idx)
    for mem in valid_memories:
        mem.id = None
        mem.chat_session_id = saved_fork.id
        mem_repo.add_memory(mem)

    return jsonify(
        {
            "forked_session_id": saved_fork.id,
            "title": saved_fork.title,
        }
    ), 201


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>", methods=["DELETE"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_messages_from_idx(session_id: int, message_idx: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()
    wi_repo = WorldInfoRepository()

    all_before_delete = chat_repo.get_messages(session_id, limit=None)
    msgs_to_delete = [m for m in all_before_delete if m.message_idx >= message_idx]
    _revert_relationship_for_messages(chat_service, chat_session, msgs_to_delete)

    deleted_msgs = chat_repo.delete_messages_after(
        session_id=session_id,
        message_idx=message_idx,
        inclusive=True,
    )
    deleted_mems = mem_repo.delete_after_idx(
        session_id=session_id,
        message_idx=message_idx - 1,
    )

    remaining_messages = chat_repo.get_messages(session_id, limit=None)
    chat_service.recalculate_current_location_after_deletion(chat_session, remaining_messages)
    chat_service.recalculate_events_after_deletion(chat_session, remaining_messages)
    chat_repo.update_session(chat_session)

    curr_loc = (
        wi_repo.get_location(chat_session.current_location_id)
        if chat_session.current_location_id
        else None
    )

    return jsonify(
        {
            "deleted_messages": deleted_msgs,
            "deleted_memories": deleted_mems,
            "current_location_id": chat_session.current_location_id,
            "current_location": {
                "id": curr_loc.id,
                "name": curr_loc.name,
                "background_image_path": curr_loc.background_image_path,
            } if curr_loc else None,
        }
    )


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>", methods=["PUT"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def edit_message(session_id: int, message_idx: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    new_text = str(data.get("content", "")).strip()
    if not new_text:
        return jsonify({"error": "Message content must not be empty."}), 400

    chat_repo = ChatRepository()
    trans_repo = TranslationRepository()
    trans_service = TranslationService()

    msg = chat_repo.get_message_by_idx(session_id, message_idx)
    if msg is None:
        return jsonify({"error": "Message not found."}), 404

    if msg.english_content:
        old_hash = trans_service.compute_source_hash(msg.english_content)
        trans_repo.invalidate(old_hash)

    msg.english_content = new_text
    msg.localized_content = new_text
    chat_repo.update_message(msg)

    return jsonify(
        {
            "message_idx": msg.message_idx,
            "english_content": msg.english_content,
            "localized_content": msg.localized_content,
        }
    )


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>/translate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def translate_chat_message(session_id: int, message_idx: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    target_lang = str(data.get("target_language") or data.get("language") or "de").strip().lower()

    chat_repo = ChatRepository()
    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()
    trans_service = TranslationService()

    msg = chat_repo.get_message_by_idx(session_id, message_idx)
    if msg is None:
        return jsonify({"error": "Message not found."}), 404

    source_text = (msg.english_content or msg.localized_content or "").strip()
    if not source_text:
        return jsonify({"error": "Message has no translatable text."}), 400

    source_hash = trans_service.compute_source_hash(source_text)
    cached_rec = trans_repo.get_translation(source_hash, target_lang)
    if cached_rec:
        translated = cached_rec.translated_text
    else:
        settings = settings_repo.get_settings()
        llm = get_llm_provider(settings)
        translated = trans_service.translate_text(
            text=source_text,
            target_language=target_lang,
            llm_provider=llm,
            model=settings.tasks.assistant_model,
        )
        if translated:
            rec = trans_service.create_record(
                english_text=source_text,
                target_language=target_lang,
                translated_text=translated,
            )
            trans_repo.save_translation(rec)

    msg.localized_content = translated
    chat_repo.update_message(msg)

    return jsonify(
        {
            "message_idx": msg.message_idx,
            "translated_text": translated,
            "original_text": source_text,
            "target_language": target_lang,
        }
    )


@api_chat_bp.route("/translate-text", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def translate_arbitrary_text():
    data = request.get_json(silent=True) or request.form.to_dict()
    source_text = str(data.get("text", "")).strip()
    target_lang = str(data.get("target_language", "de")).strip().lower()
    entity_type = str(data.get("entity_type", "")).strip()
    entity_id_raw = data.get("entity_id")
    field_name = str(data.get("field_name", "")).strip()

    if not source_text:
        return jsonify({"error": "Text is required."}), 400

    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()
    trans_service = TranslationService()

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)
    translated = trans_service.translate_text(
        text=source_text,
        target_language=target_lang,
        llm_provider=llm,
        model=settings.tasks.assistant_model,
    )

    if translated:
        rec = trans_service.create_record(
            english_text=source_text,
            target_language=target_lang,
            translated_text=translated,
        )
        trans_repo.save_translation(rec)

        if entity_type and field_name and entity_id_raw is not None and str(entity_id_raw).isdigit():
            trans_repo.save_field_translation(
                entity_type=entity_type,
                entity_id=int(entity_id_raw),
                field_name=field_name,
                language=target_lang,
                text_content=translated,
                is_outdated=False,
            )

    return jsonify(
        {
            "translated_text": translated,
            "target_language": target_lang,
        }
    )


@api_chat_bp.route("/<int:session_id>/memories", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def list_session_memories(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    mem_repo = MemoryRepository()
    memories = mem_repo.list_for_session(session_id)
    return jsonify(
        {
            "memories": [
                {
                    "id": m.id,
                    "message_idx": m.message_idx,
                    "title": m.title,
                    "tags": m.tags,
                    "summary": m.summary,
                }
                for m in memories
            ]
        }
    )


@api_chat_bp.route("/<int:session_id>/memories/<int:memory_id>/recalculate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def recalculate_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    settings_repo = SettingsRepository()
    mem_service = MemoryService()

    target_memory = mem_repo.get_by_id(memory_id)
    if target_memory is None or target_memory.chat_session_id != session_id:
        return jsonify({"error": "Memory not found."}), 404

    all_messages = chat_repo.get_messages(session_id, limit=None)
    narrative_msgs = mem_service.filter_narrative_messages(all_messages)
    all_memories = mem_repo.list_for_session(session_id)

    chunk = mem_service.extract_messages_for_memory(
        memories=all_memories,
        target_memory=target_memory,
        all_narrative_messages=narrative_msgs,
        chunk_size=10,
    )

    if not chunk:
        return jsonify({"error": "No narrative messages found for this memory episode."}), 400

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)

    msg_dicts = [
        {"role": m.role.value, "content": m.english_content or m.localized_content or ""}
        for m in chunk
    ]

    try:
        title, tags, summary, _ = mem_service.extract_memory_and_title(
            last_10_messages=msg_dicts,
            memory_prompt=settings.prompts.memory_prompt,
            llm_provider=llm,
            model=settings.tasks.memory_model,
            params=settings.params,
        )
    except Exception as exc:
        return jsonify({"error": f"LLM memory generation failed: {exc}"}), 502

    try:
        mem_service.update_memory(
            memory=target_memory,
            title=title,
            tags=tags,
            summary=summary,
        )
        mem_repo.update_memory(target_memory)
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "id": target_memory.id,
            "chat_session_id": target_memory.chat_session_id,
            "message_idx": target_memory.message_idx,
            "title": target_memory.title,
            "tags": target_memory.tags,
            "summary": target_memory.summary,
            "messages_count": len(chunk),
        }
    )


@api_chat_bp.route("/<int:session_id>/memories/<int:memory_id>/translate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def translate_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    mem_repo = MemoryRepository()
    settings_repo = SettingsRepository()
    mem_service = MemoryService()
    trans_service = TranslationService()

    target_memory = mem_repo.get_by_id(memory_id)
    if target_memory is None or target_memory.chat_session_id != session_id:
        return jsonify({"error": "Memory not found."}), 404

    data = request.get_json(silent=True) or {}
    target_lang = str(data.get("target_language") or user.language or "en").strip().lower()[:2]

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)
    model = settings.tasks.assistant_model

    try:
        translated_title = (
            trans_service.translate_text_or_none(
                text=target_memory.title,
                target_language=target_lang,
                llm_provider=llm,
                model=model,
            )
            if target_memory.title
            else None
        )
        translated_summary = (
            trans_service.translate_text_or_none(
                text=target_memory.summary,
                target_language=target_lang,
                llm_provider=llm,
                model=model,
            )
            if target_memory.summary
            else None
        )
        translated_tags = list(target_memory.tags)
        if target_memory.tags:
            raw_tags = trans_service.translate_text_or_none(
                text=", ".join(target_memory.tags),
                target_language=target_lang,
                llm_provider=llm,
                model=model,
            )
            if raw_tags:
                from shared.utils import parse_tags
                parsed = parse_tags(raw_tags)
                if parsed:
                    translated_tags = parsed
    except Exception as exc:
        return jsonify({"error": f"LLM memory translation failed: {exc}"}), 502

    new_title = translated_title or target_memory.title
    new_summary = translated_summary or target_memory.summary
    if target_memory.summary and translated_summary is None and translated_title is None:
        return jsonify({"error": "Translation failed. Please check the Assistant LLM."}), 502

    try:
        mem_service.update_memory(
            memory=target_memory,
            title=new_title,
            tags=translated_tags,
            summary=new_summary,
        )
        mem_repo.update_memory(target_memory)
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "id": target_memory.id,
            "chat_session_id": target_memory.chat_session_id,
            "message_idx": target_memory.message_idx,
            "title": target_memory.title,
            "tags": target_memory.tags,
            "summary": target_memory.summary,
            "target_language": target_lang,
        }
    )


@api_chat_bp.route("/<int:session_id>/lorebooks", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def get_session_lorebooks(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
    lb_repo = LorebookRepository()

    character = char_repo.get_by_id(chat_session.character_id)
    worldinfo = (
        wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if chat_session.active_worldinfo_id
        else None
    )

    char_lb_ids = set(character.linked_lorebook_ids) if character else set()
    wi_lb_id = worldinfo.lorebook_id if (worldinfo and worldinfo.lorebook_id) else None

    # Default lorebook IDs
    default_ids = set(char_lb_ids)
    if wi_lb_id:
        default_ids.add(wi_lb_id)

    # All visible lorebooks for the user
    all_visible = lb_repo.list_visible(user.id)
    all_map = {lb.id: lb for lb in all_visible if lb.id is not None}

    char_conditions = getattr(character, "lorebook_world_conditions", {}) or {}

    def _format_lb(
        lb,
        source: str,
        is_active: bool = True,
        is_locked: bool = False,
        required_worldinfo_id: int | None = None,
        required_worldinfo_name: str | None = None,
    ):
        entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
        all_tags: set[str] = set()
        for e in entries:
            all_tags.update(e.tags)
        return {
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "source": source,
            "is_active": is_active,
            "is_locked": is_locked,
            "required_worldinfo_id": required_worldinfo_id,
            "required_worldinfo_name": required_worldinfo_name,
        }

    default_lorebooks = []
    for lb_id in sorted(default_ids):
        lb = all_map.get(lb_id) or lb_repo.get_by_id(lb_id)
        if lb:
            in_char = lb_id in char_lb_ids
            in_wi = lb_id == wi_lb_id
            if in_char and in_wi:
                source = "character & worldinfo"
            elif in_char:
                source = "character"
            else:
                source = "worldinfo"

            is_locked = False
            req_wi_id = None
            req_wi_name = None
            if in_char and lb_id in char_conditions:
                req_wi_id = char_conditions[lb_id]
                req_wi = wi_repo.get_by_id(req_wi_id)
                req_wi_name = req_wi.name if req_wi else f"Welt #{req_wi_id}"
                if chat_session.active_worldinfo_id != req_wi_id:
                    is_locked = True

            if is_locked:
                is_active = False
            else:
                is_active = lb.id not in chat_session.disabled_lorebook_ids

            default_lorebooks.append(
                _format_lb(
                    lb,
                    source,
                    is_active=is_active,
                    is_locked=is_locked,
                    required_worldinfo_id=req_wi_id,
                    required_worldinfo_name=req_wi_name,
                )
            )

    # Alphabetical sort within default lorebooks
    default_lorebooks.sort(key=lambda x: x["name"].lower())

    custom_lorebooks = []
    for lb_id in chat_session.custom_lorebook_ids:
        if lb_id in default_ids:
            continue
        lb = all_map.get(lb_id) or lb_repo.get_by_id(lb_id)
        if lb:
            is_active = lb.id not in chat_session.disabled_lorebook_ids
            custom_lorebooks.append(_format_lb(lb, "custom", is_active=is_active))

    # Alphabetical sort within custom lorebooks
    custom_lorebooks.sort(key=lambda x: x["name"].lower())

    active_in_session_ids = default_ids.union(chat_session.custom_lorebook_ids)
    available_lorebooks = []
    for lb in sorted(all_visible, key=lambda x: x.name.lower()):
        entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
        all_tags: set[str] = set()
        for e in entries:
            all_tags.update(e.tags)
        available_lorebooks.append({
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "is_added": lb.id in active_in_session_ids,
        })

    active_count = len([x for x in default_lorebooks if x["is_active"]]) + len(
        [x for x in custom_lorebooks if x["is_active"]]
    )

    return jsonify({
        "session_id": session_id,
        "default_lorebooks": default_lorebooks,
        "custom_lorebooks": custom_lorebooks,
        "available_lorebooks": available_lorebooks,
        "active_count": active_count,
    })


@api_chat_bp.route("/<int:session_id>/lorebooks/toggle", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def toggle_session_lorebook(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    lorebook_id = data.get("lorebook_id")
    if lorebook_id is None:
        lorebook_id = request.form.get("lorebook_id")
    if lorebook_id is None:
        return jsonify({"error": "lorebook_id is required."}), 400

    try:
        lb_id = int(lorebook_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid lorebook_id."}), 400

    active = data.get("active")
    if active is None:
        active = request.form.get("active", "true").lower() in ("true", "1")
    else:
        active = bool(active)

    if active:
        char_repo = CharacterRepository()
        char = char_repo.get_by_id(chat_session.character_id)
        if char and getattr(char, "lorebook_world_conditions", None):
            req_wi_id = char.lorebook_world_conditions.get(lb_id)
            if req_wi_id is not None and req_wi_id != chat_session.active_worldinfo_id:
                return jsonify({
                    "error": "Dieses Lorebook erfordert eine andere Welt und kann in dieser Sitzung nicht aktiviert werden."
                }), 400

    chat_service = ChatService()
    chat_service.toggle_lorebook(chat_session, lb_id, active)

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "lorebook_id": lb_id,
        "is_active": active,
    })


@api_chat_bp.route("/<int:session_id>/lorebooks/custom", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def add_session_custom_lorebook(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    lorebook_id = data.get("lorebook_id")
    if lorebook_id is None:
        lorebook_id = request.form.get("lorebook_id")
    if lorebook_id is None:
        return jsonify({"error": "lorebook_id is required."}), 400

    try:
        lb_id = int(lorebook_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid lorebook_id."}), 400

    lb_repo = LorebookRepository()
    lb = lb_repo.get_by_id(lb_id)
    if lb is None or not lb.is_visible_to_user(user.id, is_admin):
        return jsonify({"error": "Lorebook not found or no access."}), 404

    chat_service = ChatService()
    chat_service.add_custom_lorebook(chat_session, lb_id)

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
    all_tags: set[str] = set()
    for e in entries:
        all_tags.update(e.tags)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "lorebook": {
            "id": lb.id,
            "name": lb.name,
            "description": lb.description,
            "tags": sorted(all_tags),
            "entry_count": len(entries),
            "source": "custom",
            "is_active": True,
        },
    }), 201


@api_chat_bp.route("/<int:session_id>/lorebooks/custom/<int:lorebook_id>", methods=["DELETE"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def remove_session_custom_lorebook(session_id: int, lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    chat_service = ChatService()
    chat_service.remove_custom_lorebook(chat_session, lorebook_id)

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "lorebook_id": lorebook_id,
    })


@api_chat_bp.route("/<int:session_id>/thinking", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def toggle_session_thinking(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    data = request.get_json(silent=True) or {}
    raw_val = data.get("thinking_enabled")
    if raw_val is None:
        raw_val = request.form.get("thinking_enabled")

    if raw_val is None:
        chat_session.thinking_enabled = not chat_session.thinking_enabled
    else:
        chat_session.thinking_enabled = bool(raw_val and str(raw_val).lower() not in ("0", "false", "off"))

    chat_repo = ChatRepository()
    chat_repo.update_session(chat_session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "thinking_enabled": chat_session.thinking_enabled,
    })

