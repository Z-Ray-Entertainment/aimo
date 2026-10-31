from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import uuid

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.auth.decorators import get_current_user, require_permission
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
from shared.utils import parse_tags

api_chat_bp = Blueprint("api_chat", __name__, url_prefix="/api/chat")

_ACTIVE_IMAGE_TASKS: dict[int, str] = {}
_PENDING_PROMPTS: dict[int, dict] = {}


def _extract_active_tags(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9äöüÄÖÜß_-]{3,}", text.lower())
    return parse_tags(words)


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


def _prepare_turn_context(
    session_id: int,
    user_text: str,
    user_language: str,
    uploaded_image_file=None,
) -> dict:
    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    lb_repo = LorebookRepository()
    mem_repo = MemoryRepository()
    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()

    chat_service = ChatService()
    wi_service = WorldInfoService()
    lb_service = LorebookService()
    mem_service = MemoryService()
    trans_service = TranslationService()
    prompt_builder = PromptBuilder()
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

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)

    image_path: str | None = None
    image_alt_text: str | None = None
    if uploaded_image_file and uploaded_image_file.filename:
        image_path = storage.save_generated_image(
            uploaded_image_file.stream, uploaded_image_file.filename
        )
        try:
            resolved_img = storage.resolve_path(image_path)
            image_alt_text = llm.analyze_image(
                image_path=resolved_img,
                prompt="Describe what is shown in this image concisely in English for a roleplay conversation.",
                model=settings.tasks.vision_model,
            ).strip()
        except Exception:
            image_alt_text = "An uploaded image."

    english_user_text = trans_service.translate_to_english(
        text=user_text,
        source_language=user_language,
        llm_provider=llm,
        model=settings.tasks.assistant_model,
    )
    if english_user_text and user_text.strip():
        rec = trans_service.create_record(
            english_text=english_user_text,
            target_language=user_language,
            translated_text=user_text.strip(),
        )
        trans_repo.save_translation(rec)

    chat_service.apply_time_decay(chat_session)
    chat_service.apply_user_message_affection(chat_session)
    chat_service.lock_persona(chat_session)

    next_idx = chat_repo.get_next_message_idx(session_id)
    user_msg = Message(
        id=None,
        session_id=session_id,
        message_idx=next_idx,
        role=MessageRole.USER,
        english_content=english_user_text,
        localized_content=user_text.strip(),
        image_path=image_path,
        image_alt_text=image_alt_text,
        created_at=datetime.now(timezone.utc),
    )
    saved_user_msg = chat_repo.add_message(user_msg)

    worldinfo = (
        wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if chat_session.active_worldinfo_id
        else None
    )
    available_locations = (
        wi_repo.list_locations(worldinfo.id)
        if worldinfo and worldinfo.id is not None
        else []
    )
    current_location = (
        wi_repo.get_location(chat_session.current_location_id)
        if chat_session.current_location_id
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

    recent_messages = chat_repo.get_messages(session_id, limit=10)
    combined_context_text = " ".join(
        m.english_content for m in recent_messages[-3:]
    )
    active_tags = _extract_active_tags(combined_context_text)

    all_memories = mem_repo.list_for_session(session_id)
    matched_memories = mem_service.search_memories_by_tags(all_memories, active_tags)

    all_lorebook_entries = lb_repo.list_entries_for_lorebooks(character.linked_lorebook_ids)
    matched_lorebooks = lb_service.search_entries_by_tags(all_lorebook_entries, active_tags)

    assembled_prompt = prompt_builder.build_roleplay_prompt(
        roleplay_system_prompt=settings.prompts.roleplay_prompt,
        character=character,
        persona=persona,
        worldinfo=worldinfo,
        current_location=current_location,
        triggered_event=triggered_event,
        recent_messages=recent_messages,
        matched_memories=matched_memories,
        matched_lorebooks=matched_lorebooks,
        available_locations=available_locations,
        relationship_value=chat_session.relationship_value,
    )

    return {
        "session_id": session_id,
        "user_message": saved_user_msg,
        "assembled_prompt": assembled_prompt,
        "user_language": user_language,
        "triggered_event": (
            {"id": triggered_event.id, "title": triggered_event.title}
            if triggered_event
            else None
        ),
    }


def _stream_roleplay_response(
    session_id: int,
    assembled_prompt: str,
    user_language: str = "de",
):
    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    wi_repo = WorldInfoRepository()
    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()

    char_service = CharacterService()
    trans_service = TranslationService()
    wi_service = WorldInfoService()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None:
        yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
        return

    character = char_repo.get_by_id(chat_session.character_id)
    if character is None:
        yield f"event: error\ndata: {json.dumps({'error': 'Character not found'})}\n\n"
        return

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)

    full_english_chunks: list[str] = []
    try:
        for token in llm.generate_stream(
            prompt=assembled_prompt,
            model=settings.tasks.roleplay_model,
            params=settings.params,
        ):
            full_english_chunks.append(token)
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
    except Exception as exc:
        if not full_english_chunks:
            fallback_en = f"*{character.name} pauses thoughtfully and looks at you.*"
            full_english_chunks.append(fallback_en)
            yield f"event: token\ndata: {json.dumps({'token': fallback_en, 'fallback': str(exc)})}\n\n"

    english_reply = "".join(full_english_chunks).strip()
    yield f"event: generation_done\ndata: {json.dumps({'english_content': english_reply})}\n\n"

    emotion_candidates = [
        e.value
        for e in Emotion
        if e.name not in ("EMBERASSED", "RELIFE", "SUPRISE")
    ]
    detected_emotion_str = Emotion.NEUTRAL.value
    try:
        detected_emotion_str = llm.classify(
            text=english_reply,
            candidates=emotion_candidates,
            model=settings.tasks.roleplay_model,
        )
    except Exception:
        detected_emotion_str = Emotion.NEUTRAL.value

    detected_emotion = Emotion.resolve(detected_emotion_str)
    selected_sprite = char_service.select_sprite_for_emotion(character, detected_emotion)

    suggested_location = None
    if chat_session.active_worldinfo_id is not None:
        locations = wi_repo.list_locations(chat_session.active_worldinfo_id)
        other_locations = [
            loc for loc in locations if loc.id != chat_session.current_location_id
        ]
        if other_locations:
            loc_candidates = ["stay_here"] + [loc.name for loc in other_locations]
            try:
                loc_choice = llm.classify(
                    text=(
                        "Based on this dialogue, did the characters explicitly decide or propose "
                        f"to move to a new location? Text: {english_reply}"
                    ),
                    candidates=loc_candidates,
                    model=settings.tasks.roleplay_model,
                )
                for loc in other_locations:
                    if loc.name.lower() == loc_choice.strip().lower():
                        suggested_location = {
                            "id": loc.id,
                            "name": loc.name,
                            "background_image_path": loc.background_image_path,
                        }
                        break
            except Exception:
                pass

    cache_dict = trans_repo.get_cache_dict(user_language)
    localized_reply = trans_service.get_localized_text(
        english_text=english_reply,
        target_language=user_language,
        cache_records=cache_dict,
        llm_provider=llm,
        model=settings.tasks.assistant_model,
    )
    if english_reply and localized_reply:
        trans_rec = trans_service.create_record(
            english_text=english_reply,
            target_language=user_language,
            translated_text=localized_reply,
        )
        trans_repo.save_translation(trans_rec)

    next_idx = chat_repo.get_next_message_idx(session_id)
    ai_msg = Message(
        id=None,
        session_id=session_id,
        message_idx=next_idx,
        role=MessageRole.CHARACTER,
        english_content=english_reply,
        localized_content=localized_reply,
        emotion_tag=detected_emotion.value,
        created_at=datetime.now(timezone.utc),
    )
    saved_ai_msg = chat_repo.add_message(ai_msg)

    if chat_session.active_worldinfo_id and chat_session.events_enabled:
        cooldown_state = EventCooldownState(
            current_counter=chat_session.cooldown_counter,
            triggered_event_ids=set(chat_session.triggered_event_ids),
        )
        wi_service.decrement_cooldown(cooldown_state)
        chat_session.cooldown_counter = max(1, cooldown_state.current_counter)
        chat_repo.update_session(chat_session)

    _run_async_memory_extraction(session_id)

    payload = {
        "message_id": saved_ai_msg.id,
        "message_idx": saved_ai_msg.message_idx,
        "english_content": english_reply,
        "localized_content": localized_reply,
        "emotion": detected_emotion.value,
        "sprite_path": selected_sprite.file_path,
        "relationship_value": chat_session.relationship_value,
        "suggested_location": suggested_location,
    }
    yield f"event: message_complete\ndata: {json.dumps(payload)}\n\n"


@api_chat_bp.route("/<int:session_id>/messages", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def post_message(session_id: int):
    user = get_current_user()
    assert user is not None
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
        ctx = _prepare_turn_context(
            session_id=session_id,
            user_text=user_text,
            user_language=user_lang,
            uploaded_image_file=uploaded_file,
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    if not stream_now:
        _PENDING_PROMPTS[session_id] = ctx
        user_msg = ctx["user_message"]
        return jsonify(
            {
                "status": "ready_for_stream",
                "user_message": {
                    "id": user_msg.id,
                    "message_idx": user_msg.message_idx,
                    "localized_content": user_msg.localized_content,
                    "image_path": user_msg.image_path,
                },
                "triggered_event": ctx["triggered_event"],
            }
        )

    return Response(
        stream_with_context(
            _stream_roleplay_response(
                session_id=session_id,
                assembled_prompt=ctx["assembled_prompt"],
                user_language=user_lang,
            )
        ),
        mimetype="text/event-stream",
    )


@api_chat_bp.route("/<int:session_id>/stream", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def stream_session_response(session_id: int):
    ctx = _PENDING_PROMPTS.pop(session_id, None)
    user_lang = request.args.get("language", "de")
    if ctx is None:
        msg_text = request.args.get("message", "").strip()
        if not msg_text:
            return jsonify({"error": "No pending message for stream."}), 400
        try:
            ctx = _prepare_turn_context(
                session_id=session_id,
                user_text=msg_text,
                user_language=user_lang,
            )
        except AimoError as exc:
            return jsonify({"error": str(exc)}), 400

    return Response(
        stream_with_context(
            _stream_roleplay_response(
                session_id=session_id,
                assembled_prompt=ctx["assembled_prompt"],
                user_language=ctx["user_language"],
            )
        ),
        mimetype="text/event-stream",
    )


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

    return jsonify(
        {
            "status": "switched",
            "location": {
                "id": location.id,
                "name": location.name,
                "background_image_path": location.background_image_path,
            },
            "ui_notice": f"Ihr seid nach {location.name} gegangen",
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
    user_lang = str(data.get("language", "de")).strip()
    if not new_text:
        return jsonify({"error": "Message content must not be empty."}), 400

    chat_repo = ChatRepository()
    trans_repo = TranslationRepository()
    settings_repo = SettingsRepository()
    trans_service = TranslationService()

    msg = chat_repo.get_message_by_idx(session_id, message_idx)
    if msg is None:
        return jsonify({"error": "Message not found."}), 404

    settings = settings_repo.get_settings()
    llm = get_llm_provider(settings)
    new_english, old_hash = trans_service.sync_text_update(
        old_english_text=msg.english_content,
        new_user_text=new_text,
        user_language=user_lang,
        llm_provider=llm,
        model=settings.tasks.assistant_model,
    )
    if old_hash:
        trans_repo.invalidate(old_hash)

    msg.english_content = new_english
    msg.localized_content = new_text
    chat_repo.update_message(msg)

    if new_english:
        rec = trans_service.create_record(
            english_text=new_english,
            target_language=user_lang,
            translated_text=new_text,
        )
        trans_repo.save_translation(rec)

    return jsonify(
        {
            "message_idx": msg.message_idx,
            "english_content": msg.english_content,
            "localized_content": msg.localized_content,
        }
    )
