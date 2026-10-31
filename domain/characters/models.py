from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from domain.personas.models import Gender

_EMOTION_ALIASES: dict[str, str] = {
    "emberassed": "embarrassed",
    "relife": "relief",
    "suprise": "surprise",
}


class Emotion(StrEnum):
    ADMIRE = "admire"
    AMUSED = "amused"
    ANGER = "anger"
    ANNOYED = "annoyed"
    APPROVAL = "approval"
    CARING = "caring"
    CONFUSED = "confused"
    CURIOUS = "curious"
    DESIRE = "desire"
    DISAPPOINTED = "disappointed"
    DISAPPROVAL = "disapproval"
    DISGUST = "disgust"
    EMBARRASSED = "embarrassed"
    EXCITED = "excited"
    FEAR = "fear"
    GRATITUDE = "gratitude"
    GRIEF = "grief"
    JOY = "joy"
    LOVE = "love"
    NERVOUSNESS = "nervousness"
    NEUTRAL = "neutral"
    OPTIMISTIC = "optimistic"
    PRIDE = "pride"
    REALIZE = "realize"
    RELIEF = "relief"
    REMORSE = "remorse"
    SAD = "sad"
    SURPRISE = "surprise"

    # Aliases mentioned in spec
    EMBERASSED = "embarrassed"
    RELIFE = "relief"
    SUPRISE = "surprise"

    @classmethod
    def resolve(cls, raw: str | "Emotion") -> "Emotion":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, str):
            return cls.NEUTRAL
        cleaned = raw.strip().lower()
        cleaned = _EMOTION_ALIASES.get(cleaned, cleaned)
        for member in cls:
            if cleaned == member.value or cleaned.upper() == member.name:
                return member
        return cls.NEUTRAL


@dataclass
class EmotionalSprite:
    emotion: Emotion
    variant: int
    file_path: str
    id: int | None = None
    character_id: int | None = None


@dataclass
class CharacterImage:
    id: int | None
    character_id: int
    file_path: str
    unlock_threshold: int


@dataclass
class Character:
    id: int | None
    user_id: int
    name: str
    gender: Gender
    primary_portrait_path: str
    description: str
    first_message: str
    visibility: str = "private"
    dialogue_examples: list[str] = field(default_factory=list)
    linked_lorebook_ids: list[int] = field(default_factory=list)
    suggested_worldinfo_id: int | None = None
    initial_location_id: int | None = None
    initial_relationship: int = 0
    preferred_location_ids: list[int] = field(default_factory=list)
    disliked_location_ids: list[int] = field(default_factory=list)
    gallery_images: list[CharacterImage] = field(default_factory=list)
    sprites: list[EmotionalSprite] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
