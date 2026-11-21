from __future__ import annotations

from datetime import datetime, timezone

from application.chat_services.memory_orchestrator import run_async_memory_extraction
from application.chat_services.task_registry import (
    _TASKS_LOCK,
    _USER_NOTIFICATIONS,
    BackgroundTurnTask,
    record_admin_prompt,
)
from domain.characters.models import Character, Emotion
from domain.characters.services import CharacterService
from domain.chat.models import ChatSession, Message, MessageRole
from domain.chat.relationship import RelationshipImpact
from domain.chat.services import ChatService
from domain.personas.models import UserPersona
from domain.settings.models import ServiceSettings
from domain.validation import DomainValidator
from domain.worldinfo.models import Location
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from shared.utils import replace_roleplay_placeholders


def clean_streamed_reply(
    raw_chunks: list[str],
    stop_sequences: list[str],
    character: Character,
    persona: UserPersona,
) -> str:
    raw_reply = "".join(raw_chunks).strip()
    cleaned_narrative = DomainValidator.strip_llm_thinking_tags(raw_reply)
    if cleaned_narrative:
        raw_reply = cleaned_narrative

    for stop_seq in stop_sequences:
        if stop_seq.strip() and stop_seq in raw_reply:
            raw_reply = raw_reply.split(stop_seq)[0].strip()

    return replace_roleplay_placeholders(
        raw_reply,
        character.name,
        persona.name,
        character_gender=character.gender.value,
        persona_gender=persona.gender.value,
    )


def finalize_streamed_turn(
    *,
    task: BackgroundTurnTask,
    session: ChatSession,
    character: Character,
    settings: ServiceSettings,
    llm,
    available_locations: list[Location],
    english_reply: str,
    cleaned_user_text: str,
    target_ai_idx: int | None,
) -> dict | None:
    assert session.id is not None
    chat_repo = ChatRepository()
    rel_repo = RelationshipRepository()
    char_service = CharacterService()
    chat_service = ChatService()

    emotion_candidates = None
    if character.sprites:
        distinct_emotions = {sp.emotion for sp in character.sprites}
        if len(distinct_emotions) > 1 or (
            len(distinct_emotions) == 1 and Emotion.NEUTRAL not in distinct_emotions
        ):
            emotion_candidates = sorted(
                {e.value for e in distinct_emotions} | {Emotion.NEUTRAL.value}
            )

    other_locations = [
        loc for loc in available_locations if loc.id != session.current_location_id
    ]
    loc_candidates = ["stay_here"] + [loc.name for loc in other_locations] if other_locations else None

    classification_model = (
        settings.tasks.classification_model
        if settings.tasks.classification_model
        else settings.tasks.roleplay_model
    )
    effective_cls_ctx = (
        settings.params.num_ctx if classification_model == settings.tasks.roleplay_model else 2048
    )

    detected_emotion_str = Emotion.NEUTRAL.value
    matched_loc_name = None
    raw_impact = RelationshipImpact.NEUTRAL.value
    current_tier_en = rel_repo.get_tier(session.relationship_value, language="en")
    try:
        detected_emotion_str, matched_loc_name, raw_impact = llm.classify_turn(
            text=english_reply,
            emotion_candidates=emotion_candidates,
            location_candidates=loc_candidates,
            model=classification_model,
            user_text=cleaned_user_text,
            character_name=character.name,
            relationship_tier=current_tier_en.name,
            evaluate_relationship=True,
            num_ctx=effective_cls_ctx,
        )
    except Exception:
        pass

    detected_emotion = Emotion.resolve(detected_emotion_str)
    impact = RelationshipImpact.resolve(raw_impact)
    selected_sprite = char_service.select_sprite_for_emotion(character, detected_emotion)

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

    if task.is_aborted:
        with task.condition:
            task.status = "aborted"
            task.condition.notify_all()
        return None

    latest_session = chat_repo.get_session(session.id) or session
    applied_delta = chat_service.apply_relationship_impact(latest_session, impact)
    chat_repo.update_session(latest_session)

    ai_next_idx = (
        target_ai_idx
        if target_ai_idx is not None
        else chat_repo.get_next_message_idx(session.id)
    )
    ai_msg = Message(
        id=None,
        session_id=session.id,
        message_idx=ai_next_idx,
        role=MessageRole.CHARACTER,
        content=english_reply,
        emotion_tag=detected_emotion.value,
        metadata={
            "relationship_impact": impact.value,
            "relationship_delta": applied_delta,
        },
        created_at=datetime.now(timezone.utc),
    )
    saved_ai_msg = chat_repo.add_message(ai_msg)
    if task.is_admin and task.assembled_prompt:
        record_admin_prompt(session.id, saved_ai_msg.message_idx, task.assembled_prompt)

    run_async_memory_extraction(session.id)

    tier = rel_repo.get_tier(latest_session.relationship_value, language=task.user_language)
    payload: dict = {
        "notification_id": task.task_id,
        "message_id": saved_ai_msg.id,
        "message_idx": saved_ai_msg.message_idx,
        "content": english_reply,
        "english_content": english_reply,
        "localized_content": english_reply,
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
        user_notifs = _USER_NOTIFICATIONS.setdefault(session.user_id, [])
        user_notifs.append(
            {
                "id": task.task_id,
                "session_id": session.id,
                "session_title": latest_session.title,
                "character_id": character.id,
                "character_name": character.name,
                "character_portrait": character.avatar_path or character.primary_portrait_path,
                "message_id": saved_ai_msg.id,
                "message_idx": saved_ai_msg.message_idx,
                "localized_content": english_reply,
                "emotion": detected_emotion.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return payload
