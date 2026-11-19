from datetime import datetime, timezone

from domain.lorebooks.exceptions import InvalidLorebookDataError
from domain.lorebooks.models import Lorebook, LorebookEntry
from domain.validation import DomainValidator
from shared.utils import count_tags_overlap, parse_tags, tags_overlap


class LorebookService:
    def create_lorebook(
        self,
        user_id: int,
        name: str,
        description: str = "",
        visibility: str = "private",
        collaborator_creator_tags: list[str] | None = None,
        is_proper_noun: bool = False,
    ) -> Lorebook:
        DomainValidator.validate_positive_user_id(user_id, InvalidLorebookDataError)
        cleaned_name = DomainValidator.validate_required_string(name, "Lorebook name", InvalidLorebookDataError)
        cleaned_desc = description.strip() if isinstance(description, str) else ""
        cleaned_vis = DomainValidator.normalize_visibility(visibility)

        return Lorebook(
            id=None,
            user_id=user_id,
            name=cleaned_name,
            description=cleaned_desc,
            visibility=cleaned_vis,
            collaborator_creator_tags=[
                t.strip().lower() for t in collaborator_creator_tags
                if isinstance(t, str) and t.strip()
            ] if collaborator_creator_tags else [],
            is_proper_noun=bool(is_proper_noun),
            created_at=datetime.now(timezone.utc),
        )

    def update_lorebook(
        self,
        lorebook: Lorebook,
        name: str,
        description: str,
        visibility: str | None = None,
        collaborator_creator_tags: list[str] | None = None,
        is_proper_noun: bool | None = None,
    ) -> Lorebook:
        lorebook.name = DomainValidator.validate_required_string(name, "Lorebook name", InvalidLorebookDataError)
        lorebook.description = description.strip() if isinstance(description, str) else ""
        if visibility is not None:
            lorebook.visibility = DomainValidator.normalize_visibility(visibility)
        if collaborator_creator_tags is not None:
            lorebook.collaborator_creator_tags = [
                t.strip().lower() for t in collaborator_creator_tags
                if isinstance(t, str) and t.strip()
            ]
        if is_proper_noun is not None:
            lorebook.is_proper_noun = bool(is_proper_noun)
        return lorebook

    def add_entry(
        self,
        lorebook_id: int,
        title: str,
        tags: list[str] | str,
        content: str,
        visibility: str = "public",
        is_proper_noun: bool = False,
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

        cleaned_vis = DomainValidator.normalize_visibility(visibility)

        now = datetime.now(timezone.utc)
        return LorebookEntry(
            id=None,
            lorebook_id=lorebook_id,
            title=cleaned_title,
            tags=normalized_tags,
            content=cleaned_content,
            visibility=cleaned_vis,
            is_proper_noun=bool(is_proper_noun),
            created_at=now,
            updated_at=now,
        )

    def update_entry(
        self,
        entry: LorebookEntry,
        title: str,
        tags: list[str] | str,
        content: str,
        visibility: str | None = None,
        is_proper_noun: bool | None = None,
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
        if visibility is not None:
            entry.visibility = DomainValidator.normalize_visibility(visibility)
        if is_proper_noun is not None:
            entry.is_proper_noun = bool(is_proper_noun)
        entry.updated_at = datetime.now(timezone.utc)
        return entry

    def delete_entry(self, entry: LorebookEntry) -> None:
        if entry is None:
            raise InvalidLorebookDataError("Lorebook entry to delete must not be None.")

    def search_entries_by_tags(
        self,
        entries: list[LorebookEntry],
        active_tags: list[str],
        latest_tags: list[str] | None = None,
        focus_keywords: frozenset[str] | set[str] | list[str] | None = None,
        preferred_lorebook_ids: set[int] | list[int] | None = None,
        max_results: int | None = None,
    ) -> list[LorebookEntry]:
        normalized_active = parse_tags(active_tags)
        if not normalized_active:
            return []
        normalized_latest = parse_tags(latest_tags) if latest_tags else []
        focus_list = list(focus_keywords) if focus_keywords else []
        pref_set = set(preferred_lorebook_ids) if preferred_lorebook_ids else set()

        scored: list[tuple[float, int, LorebookEntry]] = []
        for idx, entry in enumerate(entries):
            overlap = count_tags_overlap(entry.tags, normalized_active)
            if overlap <= 0:
                continue
            freshness = count_tags_overlap(entry.tags, normalized_latest) * 20.0 if normalized_latest else 0.0
            focus_hit = count_tags_overlap(entry.tags, focus_list) * 8.0 if focus_list else 0.0
            source_bonus = 20.0 if pref_set and entry.lorebook_id in pref_set else 0.0
            score = (overlap * 10.0) + freshness + focus_hit + source_bonus
            scored.append((score, -idx, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        matched = [item[2] for item in scored]
        if max_results is not None and max_results > 0:
            return matched[:max_results]
        return matched
