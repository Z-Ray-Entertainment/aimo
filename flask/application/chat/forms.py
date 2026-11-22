from dataclasses import dataclass, field
from typing import Any

from security import RequestDataParser


@dataclass
class StartChatForm:
    persona_id: int = 0
    worldinfo_id: int | None = None
    title: str = ""
    disabled_lorebook_ids: list[int] = field(default_factory=list)
    custom_lorebook_ids: list[int] = field(default_factory=list)
    thinking_enabled: bool = False

    @classmethod
    def from_request(cls, form_data: Any) -> "StartChatForm":
        p = RequestDataParser
        return cls(
            persona_id=p.to_opt_int(form_data, "persona_id") or 0,
            worldinfo_id=p.to_opt_int(form_data, "worldinfo_id"),
            title=p.to_str(form_data, "title"),
            disabled_lorebook_ids=p.to_int_list(form_data, "disabled_lorebook_ids"),
            custom_lorebook_ids=p.to_int_list(form_data, "custom_lorebook_ids"),
            thinking_enabled=p.to_bool(form_data, "thinking_enabled"),
        )


@dataclass
class MemoryEditForm:
    title: str = ""
    tags: str = ""
    summary: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "MemoryEditForm":
        p = RequestDataParser
        return cls(
            title=p.to_str(form_data, "title"),
            tags=p.to_str(form_data, "tags"),
            summary=p.to_str(form_data, "summary"),
        )
