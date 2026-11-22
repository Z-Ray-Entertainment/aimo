from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from domain.base import PublishableEntityMixin, ResolvableStrEnum, utc_now
from domain.personas.models import Gender


class Emotion(ResolvableStrEnum):
    @classmethod
    def _get_aliases(cls) -> dict[str, str]:
        return {
            "emberassed": "embarrassed",
            "relife": "relief",
            "suprise": "surprise",
        }

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
        return cls.resolve_value(raw, default=cls.NEUTRAL)


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
class Character(PublishableEntityMixin):
    id: int | None
    user_id: int
    name: str
    gender: Gender
    primary_portrait_path: str
    description: str
    first_message: str
    avatar_path: str | None = None
    card_image_path: str | None = None
    appearance: str = ""
    visibility: str = "private"
    origin_language: str = "en"
    collaborator_creator_tags: list[str] = field(default_factory=list)
    dialogue_examples: list[dict[str, str]] = field(default_factory=list)
    linked_lorebook_ids: list[int] = field(default_factory=list)
    lorebook_world_conditions: dict[int, int] = field(default_factory=dict)
    suggested_worldinfo_id: int | None = None
    initial_location_id: int | None = None
    initial_relationship: int = 0
    preferred_location_ids: list[int] = field(default_factory=list)
    disliked_location_ids: list[int] = field(default_factory=list)
    gallery_images: list[CharacterImage] = field(default_factory=list)
    sprites: list[EmotionalSprite] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

