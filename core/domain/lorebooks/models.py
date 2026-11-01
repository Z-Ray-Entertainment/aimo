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

    def is_visible_to_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.visibility == "public" or self.user_id == user_id or is_admin

    def is_editable_by_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.user_id == user_id or is_admin



@dataclass
class LorebookEntry:
    id: int | None
    lorebook_id: int
    title: str
    tags: list[str]
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
