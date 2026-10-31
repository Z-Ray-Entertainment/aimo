from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WorldInfo:
    id: int | None
    user_id: int
    name: str
    icon: str | None = None
    visibility: str = "private"
    initial_location_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
