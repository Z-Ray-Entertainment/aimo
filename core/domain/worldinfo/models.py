from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WorldInfo:
    id: int | None
    user_id: int
    name: str
    icon: str | None = "🌐"
    visibility: str = "private"
    cover_image_path: str | None = None
    lorebook_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_visible_to_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.visibility == "public" or self.user_id == user_id or is_admin

    def is_editable_by_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.user_id == user_id or is_admin



@dataclass
class Location:
    id: int | None
    worldinfo_id: int
    name: str
    tags: list[str]
    description: str
    background_image_path: str | None = None
    vision_alt_text: str | None = None


@dataclass
class Event:
    id: int | None
    worldinfo_id: int
    title: str
    probability: int
    one_shot: bool
    description: str
    location_id: int | None = None


@dataclass
class EventCooldownState:
    current_counter: int
    triggered_event_ids: set[int] = field(default_factory=set)
