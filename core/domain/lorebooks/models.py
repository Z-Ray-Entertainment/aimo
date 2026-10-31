from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Lorebook:
    id: int | None
    user_id: int
    name: str
    description: str = ""
    visibility: str = "private"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LorebookEntry:
    id: int | None
    lorebook_id: int
    title: str
    tags: list[str]
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
