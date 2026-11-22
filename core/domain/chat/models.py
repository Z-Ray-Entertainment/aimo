from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from domain.base import OwnedEntityMixin, ResolvableStrEnum, utc_now


class MessageRole(ResolvableStrEnum):
    USER = "user"
    CHARACTER = "character"
    SYSTEM = "system"

    @classmethod
    def resolve(cls, raw: str | "MessageRole") -> "MessageRole":
        return cls.resolve_value(raw, default=cls.USER)


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
    content: str
    image_path: str | None = None
    image_alt_text: str | None = None
    emotion_tag: str | None = None
    system_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    @property
    def effective_text(self) -> str:
        return (self.content or self.image_alt_text or "").strip()

    @property
    def localized_content(self) -> str:
        return self.content

    @localized_content.setter
    def localized_content(self, value: str) -> None:
        self.content = value

    @property
    def english_content(self) -> str:
        return self.content

    @english_content.setter
    def english_content(self, value: str) -> None:
        self.content = value


@dataclass
class ChatSession(OwnedEntityMixin):
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
    last_message_at: datetime = field(default_factory=utc_now)
    parent_session_id: int | None = None
    persona_locked: bool = False
    triggered_event_ids: set[int] = field(default_factory=set)
    disabled_lorebook_ids: set[int] = field(default_factory=set)
    custom_lorebook_ids: list[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
