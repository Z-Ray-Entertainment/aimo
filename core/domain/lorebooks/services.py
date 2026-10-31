from datetime import datetime, timezone

from domain.lorebooks.exceptions import InvalidLorebookDataError
from domain.lorebooks.models import Lorebook, LorebookEntry
from shared.utils import parse_tags, tags_overlap


class LorebookService:
    def create_lorebook(
        self,
        user_id: int,
        name: str,
        description: str = "",
        visibility: str = "private",
    ) -> Lorebook:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise InvalidLorebookDataError("A valid positive user_id is required.")

        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidLorebookDataError("Lorebook name must not be empty.")

        cleaned_desc = description.strip() if isinstance(description, str) else ""
        cleaned_vis = "public" if isinstance(visibility, str) and visibility.strip().lower() == "public" else "private"

        return Lorebook(
            id=None,
            user_id=user_id,
            name=cleaned_name,
            description=cleaned_desc,
            visibility=cleaned_vis,
            created_at=datetime.now(timezone.utc),
        )

    def update_lorebook(
        self,
        lorebook: Lorebook,
        name: str,
        description: str,
        visibility: str | None = None,
    ) -> Lorebook:
        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidLorebookDataError("Lorebook name must not be empty.")

        lorebook.name = cleaned_name
        lorebook.description = description.strip() if isinstance(description, str) else ""
        if visibility is not None:
            lorebook.visibility = (
                "public" if isinstance(visibility, str) and visibility.strip().lower() == "public" else "private"
            )
        return lorebook

    def add_entry(
        self,
        lorebook_id: int,
        title: str,
        tags: list[str] | str,
        content: str,
    ) -> LorebookEntry:
        if isinstance(lorebook_id, bool) or not isinstance(lorebook_id, int) or lorebook_id <= 0:
            raise InvalidLorebookDataError("A valid positive lorebook_id is required.")

        cleaned_title = title.strip() if isinstance(title, str) else ""
        if not cleaned_title:
            raise InvalidLorebookDataError("Lorebook entry title must not be empty.")

        normalized_tags = parse_tags(tags)
        if not normalized_tags:
            raise InvalidLorebookDataError("Lorebook entry must have at least one tag.")

        cleaned_content = content.strip() if isinstance(content, str) else ""
        if not cleaned_content:
            raise InvalidLorebookDataError("Lorebook entry content must not be empty.")

        now = datetime.now(timezone.utc)
        return LorebookEntry(
            id=None,
            lorebook_id=lorebook_id,
            title=cleaned_title,
            tags=normalized_tags,
            content=cleaned_content,
            created_at=now,
            updated_at=now,
        )

    def update_entry(
        self,
        entry: LorebookEntry,
        title: str,
        tags: list[str] | str,
        content: str,
    ) -> LorebookEntry:
        cleaned_title = title.strip() if isinstance(title, str) else ""
        if not cleaned_title:
            raise InvalidLorebookDataError("Lorebook entry title must not be empty.")

        normalized_tags = parse_tags(tags)
        if not normalized_tags:
            raise InvalidLorebookDataError("Lorebook entry must have at least one tag.")

        cleaned_content = content.strip() if isinstance(content, str) else ""
        if not cleaned_content:
            raise InvalidLorebookDataError("Lorebook entry content must not be empty.")

        entry.title = cleaned_title
        entry.tags = normalized_tags
        entry.content = cleaned_content
        entry.updated_at = datetime.now(timezone.utc)
        return entry

    def delete_entry(self, entry: LorebookEntry) -> None:
        if entry is None:
            raise InvalidLorebookDataError("Lorebook entry to delete must not be None.")

    def search_entries_by_tags(
        self,
        entries: list[LorebookEntry],
        active_tags: list[str],
    ) -> list[LorebookEntry]:
        normalized_active = parse_tags(active_tags)
        if not normalized_active:
            return []
        return [
            entry
            for entry in entries
            if tags_overlap(entry.tags, normalized_active)
        ]
