from dataclasses import dataclass, field
from datetime import datetime

from domain.base import PublishableEntityMixin, utc_now


@dataclass
class WorldInfo(PublishableEntityMixin):
    id: int | None
    user_id: int
    name: str
    icon: str | None = "🌐"
    visibility: str = "private"
    origin_language: str = "en"
    cover_image_path: str | None = None
    backdrop_image_path: str | None = None
    lorebook_id: int | None = None
    collaborator_creator_tags: list[str] = field(default_factory=list)
    is_proper_noun: bool = False
    created_at: datetime = field(default_factory=utc_now)



@dataclass
class Location:
    id: int | None
    worldinfo_id: int
    name: str
    tags: list[str]
    description: str
    background_image_path: str | None = None
    vision_alt_text: str | None = None
    character_id: int | None = None
    is_proper_noun: bool = False

    def is_accessible_by_character(self, character_id: int | None) -> bool:
        if self.character_id is None:
            return True
        return character_id == self.character_id


@dataclass
class Event:
    id: int | None
    worldinfo_id: int | None
    title: str
    probability: int
    one_shot: bool
    description: str
    location_id: int | None = None
    character_id: int | None = None
    min_relationship: int | None = None
    max_relationship: int | None = None
    is_proper_noun: bool = False


@dataclass
class EventCooldownState:
    current_counter: int
    triggered_event_ids: set[int] = field(default_factory=set)
