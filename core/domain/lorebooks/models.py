from dataclasses import dataclass, field
from datetime import datetime

from domain.base import PublishableEntityMixin, utc_now


@dataclass
class Lorebook(PublishableEntityMixin):
    id: int | None
    user_id: int
    name: str
    description: str = ""
    visibility: str = "private"
    origin_language: str = "en"
    collaborator_creator_tags: list[str] = field(default_factory=list)
    is_proper_noun: bool = False
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class LorebookEntry:
    id: int | None
    lorebook_id: int
    title: str
    tags: list[str]
    content: str
    visibility: str = "public"
    is_proper_noun: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def is_visible_to_user(self, lorebook_owner_id: int, user_id: int, is_admin: bool = False) -> bool:
        return self.visibility == "public" or lorebook_owner_id == user_id or is_admin
