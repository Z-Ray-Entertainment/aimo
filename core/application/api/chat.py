from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import uuid

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.api.auth import get_current_user, require_permission
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.chat.models import Message, MessageRole
from domain.chat.prompt_builder import PromptBuilder
from domain.chat.services import ChatService
from domain.lorebooks.services import LorebookService
from domain.memories.services import MemoryService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters
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
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError
from shared.utils import filter_stopwords, parse_tags, replace_roleplay_placeholders

api_chat_bp = Blueprint("api_chat", __name__, url_prefix="/api/chat")

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
            narrative_msgs = [
                m
                for m in all_messages
                if m.role in (MessageRole.USER, MessageRole.CHARACTER)
            ]
            existing_memories = mem_repo.list_for_session(session_id)
            last_mem_idx = max((m.message_idx for m in existing_memories), default=0)
            unsummarized = [m for m in narrative_msgs if m.message_idx > last_mem_idx]

            if not mem_service.should_generate_memory(len(unsummarized)):
                return

            chunk = unsummarized[:10]
            target_idx = chunk[-1].message_idx
            settings = settings_repo.get_settings()
            llm = get_llm_provider(settings)

            msg_dicts = [
                {"role": m.role.value, "content": m.english_content}
                for m in chunk
            ]
            title, tags, summary, new_chat_title = mem_service.extract_memory_and_title(
                last_10_messages=msg_dicts,
                memory_prompt=settings.prompts.memory_prompt,
                llm_provider=llm,
                model=settings.tasks.memory_model,
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
        except Exception:
            pass

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _start_background_turn(
    session_id: int,
    user_text: str,
    user_language: str,
    uploaded_image_file=None,
    is_admin: bool = False,
    existing_user_msg: Message | None = None,
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
    if character is None:
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
        chat_service.apply_user_message_affection(chat_session)
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
    triggered_event = None
    if worldinfo and worldinfo.id is not None and chat_session.events_enabled:
        cooldown_state = EventCooldownState(
            current_counter=chat_session.cooldown_counter,
            triggered_event_ids=set(chat_session.triggered_event_ids),
        )
        if wi_service.decrement_cooldown(cooldown_state):
            all_events = wi_repo.list_events(worldinfo.id)
            triggered_event = wi_service.draw_event(
                worldinfo_events=all_events,
                current_location_id=chat_session.current_location_id,
                state=cooldown_state,
            )
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
    with _TASKS_LOCK:
        _BACKGROUND_TASKS[session_id] = task

    def _worker() -> None:
        w_chat_repo = ChatRepository()
        w_char_repo = CharacterRepository()
        w_persona_repo = PersonaRepository()
        w_wi_repo = WorldInfoRepository()
        w_lb_repo = LorebookRepository()
        w_mem_repo = MemoryRepository()
        w_trans_repo = TranslationRepository()
        w_settings_repo = SettingsRepository()

        w_char_service = CharacterService()
        w_wi_service = WorldInfoService()
        w_lb_service = LorebookService()
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

            if w_character.id is not None:
                w_character.description = w_trans_repo.get_localized_field(
                    "character", w_character.id, "description", "en", w_character.description
                )
                raw_default_examples = (
                    "\n".join(w_character.dialogue_examples)
                    if isinstance(w_character.dialogue_examples, list)
                    else str(w_character.dialogue_examples or "")
                )
                localized_dialogue = w_trans_repo.get_localized_field(
                    "character",
                    w_character.id,
                    "dialogue_examples",
                    "en",
                    raw_default_examples,
                )
                if isinstance(localized_dialogue, str):
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
                    "persona", w_persona.id, "description", "en", w_persona.description
                )
                w_persona.appearance = w_trans_repo.get_localized_field(
                    "persona", w_persona.id, "appearance", "en", w_persona.appearance
                )

            w_worldinfo = (
                w_wi_repo.get_by_id(w_session.active_worldinfo_id)
                if w_session.active_worldinfo_id
                else None
            )
            available_locations = (
                w_wi_repo.list_locations(w_worldinfo.id)
                if w_worldinfo and w_worldinfo.id is not None
                else []
            )
            current_location = (
                w_wi_repo.get_location(w_session.current_location_id)
                if w_session.current_location_id
                else None
            )
            if current_location and current_location.id is not None:
                current_location.description = w_trans_repo.get_localized_field(
                    "worldinfo_location",
                    current_location.id,
                    "description",
                    "en",
                    current_location.description,
                )

            if triggered_event and triggered_event.id is not None:
                triggered_event.description = w_trans_repo.get_localized_field(
                    "worldinfo_event",
                    triggered_event.id,
                    "description",
                    "en",
                    triggered_event.description,
                )

            recent_messages = w_chat_repo.get_messages(session_id, limit=10)
            combined_context_text = " ".join(
                m.english_content for m in recent_messages[-3:]
            )
            active_tags = _extract_active_tags(combined_context_text)

            all_memories = w_mem_repo.list_for_session(session_id)
            matched_memories = w_mem_service.search_memories_by_tags(all_memories, active_tags)

            all_lorebook_entries = w_lb_repo.list_entries_for_lorebooks(w_character.linked_lorebook_ids)
            matched_lorebooks = w_lb_service.search_entries_by_tags(all_lorebook_entries, active_tags)
            for lb_entry in matched_lorebooks:
                if lb_entry.id is not None:
                    lb_entry.content = w_trans_repo.get_localized_field(
                        "lorebook_entry", lb_entry.id, "content", "en", lb_entry.content
                    )

            assembled_prompt = w_prompt_builder.build_roleplay_prompt(
                roleplay_system_prompt=settings.prompts.roleplay_prompt,
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
            )
            if task.is_admin:
                task.assembled_prompt = assembled_prompt

            with task.condition:
                task.status = "streaming"
                task.condition.notify_all()

            stop_sequences = [
                f"\n{w_persona.name}:",
                f"\n{w_persona.name} (Player):",
                f"\n[{w_persona.name}]:",
                "\n[USER_PERSONA]",
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
                raw_err = str(exc)
                if (
                    "Failed to stream response from Ollama" in raw_err
                    or "Connection refused" in raw_err
                    or "Failed to establish a new connection" in raw_err
                    or "Max retries exceeded" in raw_err
                ):
                    user_friendly_err = (
                        f"Verbindung zu Ollama ({settings.tasks.roleplay_model}) fehlgeschlagen oder unterbrochen. "
                        "Bitte stelle sicher, dass der Ollama-Dienst läuft."
                    )
                elif "not found" in raw_err.lower():
                    user_friendly_err = (
                        f"Ollama-Modell '{settings.tasks.roleplay_model}' wurde nicht gefunden. "
                        f"Bitte in Ollama laden (ollama run {settings.tasks.roleplay_model})."
                    )
                else:
                    user_friendly_err = f"Ollama-Verbindungsfehler ({settings.tasks.roleplay_model}): {raw_err}"

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
                    loc for loc in locations if loc.id != w_session.current_location_id
                ]
                if other_locations:
                    loc_candidates = ["stay_here"] + [loc.name for loc in other_locations]

            classification_model = (
                settings.tasks.classification_model
                if getattr(settings.tasks, "classification_model", None)
                else settings.tasks.roleplay_model
            )

            detected_emotion_str = Emotion.NEUTRAL.value
            matched_loc_name = None
            if emotion_candidates is not None or loc_candidates is not None:
                try:
                    detected_emotion_str, matched_loc_name = llm.classify_turn(
                        text=english_reply,
                        emotion_candidates=emotion_candidates,
                        location_candidates=loc_candidates,
                        model=classification_model,
                    )
                except Exception:
                    detected_emotion_str = Emotion.NEUTRAL.value
                    matched_loc_name = None

            detected_emotion = Emotion.resolve(detected_emotion_str)
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

            source_hash = w_trans_service.compute_source_hash(english_reply)
            cached_rec = w_trans_repo.get_translation(source_hash, user_language)
            localized_reply = cached_rec.translated_text if cached_rec else english_reply

            if task.is_aborted:
                with task.condition:
                    task.status = "aborted"
                    task.condition.notify_all()
                return

            ai_next_idx = w_chat_repo.get_next_message_idx(session_id)
            ai_msg = Message(
                id=None,
                session_id=session_id,
                message_idx=ai_next_idx,
                role=MessageRole.CHARACTER,
                english_content=english_reply,
                localized_content=localized_reply,
                emotion_tag=detected_emotion.value,
                created_at=datetime.now(timezone.utc),
            )
            saved_ai_msg = w_chat_repo.add_message(ai_msg)
            if task.is_admin and task.assembled_prompt:
                _record_admin_prompt(session_id, saved_ai_msg.message_idx, task.assembled_prompt)

            latest_session = w_chat_repo.get_session(session_id) or w_session
            if latest_session.active_worldinfo_id and latest_session.events_enabled:
                cooldown_state = EventCooldownState(
                    current_counter=latest_session.cooldown_counter,
                    triggered_event_ids=set(latest_session.triggered_event_ids),
                )
                w_wi_service.decrement_cooldown(cooldown_state)
                latest_session.cooldown_counter = max(1, cooldown_state.current_counter)
                w_chat_repo.update_session(latest_session)

            _run_async_memory_extraction(session_id)

            payload = {
                "notification_id": task.task_id,
                "message_id": saved_ai_msg.id,
                "message_idx": saved_ai_msg.message_idx,
                "english_content": english_reply,
                "localized_content": localized_reply,
                "emotion": detected_emotion.value,
                "sprite_path": selected_sprite.file_path,
                "relationship_value": latest_session.relationship_value,
                "suggested_location": suggested_location,
            }
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
                        "character_portrait": w_character.primary_portrait_path,
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

    while True:
        with task.condition:
            while (
                sent_tokens >= len(task.tokens)
                and (sent_gen_done or not task.generation_done)
                and (sent_image_analyzed or not task.image_analyzed)
                and task.status not in ("completed", "error", "aborted")
            ):
                task.condition.wait(timeout=15.0)

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
    assert user is not None
    is_admin = bool(user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS))
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
            }
        )

    return Response(
        stream_with_context(_stream_from_task(task)),
        mimetype="text/event-stream",
    )


@api_chat_bp.route("/<int:session_id>/stream", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def stream_session_response(session_id: int):
    user = get_current_user()
    is_admin = bool(user and (user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS)))
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
        mimetype="text/event-stream",
    )


@api_chat_bp.route("/<int:session_id>/status", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def get_session_generation_status(session_id: int):
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


@api_chat_bp.route("/<int:session_id>/regenerate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def regenerate_turn(session_id: int):
    user = get_current_user()
    assert user is not None
    is_admin = bool(user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS))

    data = request.get_json(silent=True) or {}
    user_lang = str(data.get("language", "de")).strip()

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()

    all_messages = chat_repo.get_messages(session_id, limit=None)
    narrative_msgs = [
        m for m in all_messages if m.role in (MessageRole.USER, MessageRole.CHARACTER)
    ]
    if not narrative_msgs:
        return jsonify({"error": "Keine Nachrichten zum Neu-Generieren vorhanden."}), 400

    last_msg = narrative_msgs[-1]
    deleted_msg_idx = None

    if last_msg.role == MessageRole.CHARACTER:
        if last_msg.message_idx == 0:
            return jsonify({"error": "Die Begrüßung der KI kann nicht neu generiert werden."}), 400

        chat_repo.delete_messages_after(session_id, last_msg.message_idx, inclusive=True)
        mem_repo.delete_after_idx(session_id, last_msg.message_idx - 1)
        deleted_msg_idx = last_msg.message_idx

        updated_messages = chat_repo.get_messages(session_id, limit=None)
        user_msgs = [m for m in updated_messages if m.role == MessageRole.USER]
        if not user_msgs:
            return jsonify({"error": "Keine Spielernachricht zum Neu-Generieren gefunden."}), 400
        target_user_msg = user_msgs[-1]

    elif last_msg.role == MessageRole.USER:
        target_user_msg = last_msg
    else:
        return jsonify({"error": "Ungültiger Rollenstatus der letzten Nachricht."}), 400

    try:
        task, _, triggered_event = _start_background_turn(
            session_id=session_id,
            user_text=target_user_msg.localized_content or "",
            user_language=user_lang,
            is_admin=is_admin,
            existing_user_msg=target_user_msg,
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
    data = request.get_json(silent=True) or request.form.to_dict()
    location_id = int(data.get("location_id", 0))

    chat_repo = ChatRepository()
    wi_repo = WorldInfoRepository()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None:
        return jsonify({"error": "Chat session not found."}), 404

    location = wi_repo.get_location(location_id)
    if location is None:
        return jsonify({"error": "Location not found."}), 404

    chat_session.current_location_id = location.id
    chat_repo.update_session(chat_session)

    desc_snippet = f" — {location.description}" if location.description else ""
    return jsonify(
        {
            "status": "switched",
            "location": {
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "background_image_path": location.background_image_path,
            },
            "ui_notice": f"Ihr seid nach {location.name} gegangen{desc_snippet}",
        }
    )


@api_chat_bp.route("/<int:session_id>/generate-image", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def generate_scene_image(session_id: int):
    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    settings_repo = SettingsRepository()
    storage = FileStorage()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

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
    llm = get_llm_provider(settings)
    img_gen = get_image_gen_provider(settings)

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

    diffuser_instruction = (
        f"{settings.prompts.diffuser_prompt}\n\n"
        f"Character: {character.name} ({character.description})\n"
        f"Player Persona Appearance: {persona.appearance or persona.description}\n"
        f"Location: {location_desc}\n"
        f"Recent Scene:\n{scene_text}"
    )

    try:
        sd_prompt = llm.generate(
            prompt=diffuser_instruction,
            model=settings.tasks.assistant_model,
            params=ModelParameters(num_ctx=4096, temperature=0.5, top_p=0.9, repeat_penalty=1.05),
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
        _ACTIVE_IMAGE_TASKS.pop(session_id, None)


@api_chat_bp.route("/<int:session_id>/cancel-image", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def cancel_image(session_id: int):
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
    data = request.get_json(silent=True) or request.form.to_dict()
    fork_point_idx = int(data.get("fork_point_idx", 0))

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    chat_service = ChatService()
    mem_service = MemoryService()

    orig_session = chat_repo.get_session(session_id)
    if orig_session is None:
        return jsonify({"error": "Session not found."}), 404

    all_messages = chat_repo.get_messages(session_id, limit=None)
    forked_session, filtered_messages = chat_service.fork_session(
        session=orig_session,
        messages=all_messages,
        fork_point_idx=fork_point_idx,
    )
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
    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()

    deleted_msgs = chat_repo.delete_messages_after(
        session_id=session_id,
        message_idx=message_idx,
        inclusive=True,
    )
    deleted_mems = mem_repo.delete_after_idx(
        session_id=session_id,
        message_idx=message_idx - 1,
    )
    return jsonify(
        {
            "deleted_messages": deleted_msgs,
            "deleted_memories": deleted_mems,
        }
    )


@api_chat_bp.route("/<int:session_id>/messages/<int:message_idx>", methods=["PUT"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def edit_message(session_id: int, message_idx: int):
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
