from domain.base import utc_now
from domain.lorebooks.exceptions import InvalidLorebookDataError
from domain.lorebooks.models import Lorebook, LorebookEntry
from domain.rag import score_and_rank_tagged_items
from domain.validation import DomainValidator
from shared.utils import parse_tags


class LorebookService:
    def create_lorebook(
        self,
        user_id: int,
        name: str,
        description: str = "",
        visibility: str = "private",
        collaborator_creator_tags: list[str] | None = None,
        is_proper_noun: bool = False,
        origin_language: str = "en",
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
            origin_language=(origin_language or "en").strip().lower()[:2] or "en",
            collaborator_creator_tags=DomainValidator.normalize_collaborator_tags(collaborator_creator_tags),
            is_proper_noun=bool(is_proper_noun),
            created_at=utc_now(),
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
            lorebook.collaborator_creator_tags = DomainValidator.normalize_collaborator_tags(collaborator_creator_tags)
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
        DomainValidator.validate_positive_id(lorebook_id, "lorebook_id", InvalidLorebookDataError)
        cleaned_title = DomainValidator.validate_required_string(title, "Lorebook entry title", InvalidLorebookDataError)

        normalized_tags = parse_tags(tags)
        if not normalized_tags:
            raise InvalidLorebookDataError("Lorebook entry must have at least one tag.")

        cleaned_content = DomainValidator.validate_required_string(content, "Lorebook entry content", InvalidLorebookDataError)
        cleaned_vis = DomainValidator.normalize_visibility(visibility)

        now = utc_now()
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
        cleaned_title = DomainValidator.validate_required_string(title, "Lorebook entry title", InvalidLorebookDataError)

        normalized_tags = parse_tags(tags)
        if not normalized_tags:
            raise InvalidLorebookDataError("Lorebook entry must have at least one tag.")

        cleaned_content = DomainValidator.validate_required_string(content, "Lorebook entry content", InvalidLorebookDataError)

        entry.title = cleaned_title
        entry.tags = normalized_tags
        entry.content = cleaned_content
        if visibility is not None:
            entry.visibility = DomainValidator.normalize_visibility(visibility)
        if is_proper_noun is not None:
            entry.is_proper_noun = bool(is_proper_noun)
        entry.updated_at = utc_now()
        return entry

    def delete_entry(self, entry: LorebookEntry) -> None:
        return None

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
        focus_set = set(focus_keywords) if focus_keywords else set()
        pref_set = set(preferred_lorebook_ids) if preferred_lorebook_ids else set()

        indexed = list(enumerate(entries))
        ranked = score_and_rank_tagged_items(
            indexed,
            get_tags=lambda pair: pair[1].tags,
            get_text_parts=lambda pair: (pair[1].title, pair[1].content, " ".join(pair[1].tags)),
            get_order_key=lambda pair: -pair[0],
            active_tags=normalized_active,
            latest_user_tags=normalized_latest,
            focus_keywords=focus_set,
            extra_bonus_fn=(
                (lambda pair: 20.0 if pair[1].lorebook_id in pref_set else 0.0)
                if pref_set
                else None
            ),
            max_results=max_results if max_results and max_results > 0 else len(entries) or 1,
        )
        return [pair[1] for pair in ranked]
