from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class MessageRole(StrEnum):
    USER = "user"
    CHARACTER = "character"
    SYSTEM = "system"

    @classmethod
    def resolve(cls, raw: str | "MessageRole") -> "MessageRole":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            return cls.USER
        cleaned = raw.strip().lower()
        for member in cls:
            if cleaned == member.value or cleaned.upper() == member.name:
                return member
        return cls.USER


class SystemMessageType(StrEnum):
    GENERAL = "general"
    LOCATION_CHANGE = "location_change"
    EVENT_TRIGGER = "event_trigger"


@dataclass
class Message:
    id: int | None
    session_id: int
    message_idx: int
    role: MessageRole
    english_content: str
    localized_content: str
    image_path: str | None = None
    image_alt_text: str | None = None
    emotion_tag: str | None = None
    system_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatSession:
    id: int | None
    user_id: int
    character_id: int
    persona_id: int
    active_worldinfo_id: int | None
    current_location_id: int | None
    title: str
    initial_location_id: int | None = None
    relationship_value: float = 0.0
    events_enabled: bool = True
    thinking_enabled: bool = False
    cooldown_counter: int = 25
    last_message_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    parent_session_id: int | None = None
    persona_locked: bool = False
    triggered_event_ids: set[int] = field(default_factory=set)
    disabled_lorebook_ids: set[int] = field(default_factory=set)
    custom_lorebook_ids: list[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
