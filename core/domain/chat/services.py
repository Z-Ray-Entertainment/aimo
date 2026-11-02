from datetime import datetime, timezone
import random

from domain.characters.models import Character, Emotion
from domain.chat.exceptions import InvalidChatDataError, PersonaLockedError
from domain.chat.models import ChatSession, Message, MessageRole
from shared.utils import replace_roleplay_placeholders

MIN_RELATIONSHIP: float = -100.0
MAX_RELATIONSHIP: float = 100.0
USER_MESSAGE_AFFECTION_DELTA: float = 0.1
DAILY_DECAY_RATE: float = 0.1


class ChatService:
    def apply_user_message_affection(self, session: ChatSession) -> None:
        session.relationship_value = round(
            min(MAX_RELATIONSHIP, max(MIN_RELATIONSHIP, session.relationship_value + USER_MESSAGE_AFFECTION_DELTA)),
            4,
        )
        session.last_message_at = datetime.now(timezone.utc)

    def apply_time_decay(
        self,
        session: ChatSession,
        current_time: datetime | None = None,
    ) -> None:
        now = current_time or datetime.now(timezone.utc)
        last_time = session.last_message_at
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        elapsed_seconds = (now - last_time).total_seconds()
        if elapsed_seconds <= 0:
            return

        days = elapsed_seconds / 86400.0
        decay = DAILY_DECAY_RATE * days
        session.relationship_value = round(
            max(MIN_RELATIONSHIP, min(MAX_RELATIONSHIP, session.relationship_value - decay)),
            4,
        )

    def create_session(
        self,
        user_id: int,
        character: Character,
        persona_id: int,
        worldinfo_id: int | None = None,
        title: str | None = None,
        persona_name: str = "User",
        localized_welcome_text: str | None = None,
        initial_location_id: int | None = None,
        disabled_lorebook_ids: set[int] | None = None,
        custom_lorebook_ids: list[int] | None = None,
    ) -> tuple[ChatSession, Message]:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise InvalidChatDataError("A valid positive user_id is required.")
        if character.id is None:
            raise InvalidChatDataError("Character must have a valid ID.")
        if isinstance(persona_id, bool) or not isinstance(persona_id, int) or persona_id <= 0:
            raise InvalidChatDataError("A valid positive persona_id is required.")

        initial_rel = float(max(-100, min(100, character.initial_relationship)))
        initial_loc_id = (
            initial_location_id
            if initial_location_id is not None
            else (character.initial_location_id if worldinfo_id is not None else None)
        )
        now = datetime.now(timezone.utc)

        session = ChatSession(
            id=None,
            user_id=user_id,
            character_id=character.id,
            persona_id=persona_id,
            active_worldinfo_id=worldinfo_id,
            current_location_id=initial_loc_id,
            title=(title.strip() if title and title.strip() else f"Chat with {character.name}"),
            relationship_value=initial_rel,
            events_enabled=True,
            cooldown_counter=random.randint(10, 100),
            last_message_at=now,
            parent_session_id=None,
            persona_locked=False,
            triggered_event_ids=set(),
            disabled_lorebook_ids=set(disabled_lorebook_ids) if disabled_lorebook_ids else set(),
            custom_lorebook_ids=list(custom_lorebook_ids) if custom_lorebook_ids else [],
            created_at=now,
        )

        raw_welcome = (
            character.first_message.strip()
            if character.first_message.strip()
            else f"*{character.name} looks at you.*"
        )
        welcome_en = replace_roleplay_placeholders(raw_welcome, character.name, persona_name)
        welcome_loc = replace_roleplay_placeholders(
            (localized_welcome_text.strip() if localized_welcome_text and localized_welcome_text.strip() else raw_welcome),
            character.name,
            persona_name,
        )
        first_msg = Message(
            id=None,
            session_id=0,
            message_idx=0,
            role=MessageRole.CHARACTER,
            english_content=welcome_en,
            localized_content=welcome_loc,
            emotion_tag=Emotion.NEUTRAL.value,
            created_at=now,
        )
        return session, first_msg

    def lock_persona(self, session: ChatSession) -> None:
        session.persona_locked = True

    def change_persona(self, session: ChatSession, new_persona_id: int) -> None:
        if session.persona_locked:
            raise PersonaLockedError(
                "Persona cannot be changed after the first user message in this session."
            )
        if isinstance(new_persona_id, bool) or not isinstance(new_persona_id, int) or new_persona_id <= 0:
            raise InvalidChatDataError("A valid positive persona_id is required.")
        session.persona_id = new_persona_id

    def switch_worldinfo(
        self,
        session: ChatSession,
        new_worldinfo_id: int | None,
        initial_location_id: int | None = None,
    ) -> None:
        session.active_worldinfo_id = new_worldinfo_id
        if new_worldinfo_id is None:
            session.current_location_id = None
        else:
            session.current_location_id = initial_location_id

    def fork_session(
        self,
        session: ChatSession,
        messages: list[Message],
        fork_point_idx: int,
    ) -> tuple[ChatSession, list[Message]]:
        now = datetime.now(timezone.utc)
        filtered_messages = [
            Message(
                id=None,
                session_id=0,
                message_idx=msg.message_idx,
                role=msg.role,
                english_content=msg.english_content,
                localized_content=msg.localized_content,
                image_path=msg.image_path,
                image_alt_text=msg.image_alt_text,
                emotion_tag=msg.emotion_tag,
                created_at=msg.created_at,
            )
            for msg in messages
            if msg.message_idx <= fork_point_idx
        ]
        has_user_msg = any(m.role == MessageRole.USER for m in filtered_messages)

        forked_session = ChatSession(
            id=None,
            user_id=session.user_id,
            character_id=session.character_id,
            persona_id=session.persona_id,
            active_worldinfo_id=session.active_worldinfo_id,
            current_location_id=session.current_location_id,
            title=f"{session.title} (Fork)",
            relationship_value=session.relationship_value,
            events_enabled=session.events_enabled,
            cooldown_counter=session.cooldown_counter,
            last_message_at=now,
            parent_session_id=session.id,
            persona_locked=has_user_msg or session.persona_locked,
            triggered_event_ids=set(session.triggered_event_ids),
            disabled_lorebook_ids=set(session.disabled_lorebook_ids),
            custom_lorebook_ids=list(session.custom_lorebook_ids),
            created_at=now,
        )
        return forked_session, filtered_messages

    def toggle_lorebook(self, session: ChatSession, lorebook_id: int, active: bool) -> None:
        if active:
            session.disabled_lorebook_ids.discard(lorebook_id)
        else:
            session.disabled_lorebook_ids.add(lorebook_id)

    def add_custom_lorebook(self, session: ChatSession, lorebook_id: int) -> None:
        if lorebook_id not in session.custom_lorebook_ids:
            session.custom_lorebook_ids.append(lorebook_id)
        session.disabled_lorebook_ids.discard(lorebook_id)

    def remove_custom_lorebook(self, session: ChatSession, lorebook_id: int) -> None:
        if lorebook_id in session.custom_lorebook_ids:
            session.custom_lorebook_ids.remove(lorebook_id)
        session.disabled_lorebook_ids.discard(lorebook_id)

    def get_effective_lorebook_ids(
        self,
        session: ChatSession,
        character_lorebook_ids: list[int],
        worldinfo_lorebook_id: int | None,
        character_world_conditions: dict[int, int] | None = None,
    ) -> list[int]:
        candidates: list[int] = []
        conditions = character_world_conditions or {}
        for l_id in character_lorebook_ids:
            if l_id in conditions and conditions[l_id] != session.active_worldinfo_id:
                continue
            if l_id not in candidates:
                candidates.append(l_id)
        if worldinfo_lorebook_id is not None and worldinfo_lorebook_id not in candidates:
            candidates.append(worldinfo_lorebook_id)
        for c_id in session.custom_lorebook_ids:
            if c_id not in candidates:
                candidates.append(c_id)
        return [cid for cid in candidates if cid not in session.disabled_lorebook_ids]
