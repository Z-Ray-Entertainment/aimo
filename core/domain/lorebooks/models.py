from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Lorebook:
    id: int | None
    user_id: int
    name: str
    description: str = ""
    visibility: str = "private"
    origin_language: str = "en"
    collaborator_creator_tags: list[str] = field(default_factory=list)
    is_proper_noun: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_visible_to_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.visibility == "public" or self.user_id == user_id or is_admin

    def is_editable_by_user(
        self,
        user_id: int,
        is_admin: bool = False,
        creator_tag: str | None = None,
    ) -> bool:
        if self.user_id == user_id or is_admin:
            return True
        if creator_tag and creator_tag in self.collaborator_creator_tags:
            return True
        return False

    def is_deletable_by_user(self, user_id: int, is_admin: bool = False) -> bool:
        return self.user_id == user_id or is_admin



@dataclass
class LorebookEntry:
    id: int | None
    lorebook_id: int
    title: str
    tags: list[str]
    content: str
    visibility: str = "public"
    is_proper_noun: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_visible_to_user(self, lorebook_owner_id: int, user_id: int, is_admin: bool = False) -> bool:
        return self.visibility == "public" or lorebook_owner_id == user_id or is_admin
