from dataclasses import dataclass
from typing import Any

from shared.request_parsers import RequestDataParser


@dataclass
class StartChatForm:
    persona_id: int = 0
    worldinfo_id: int | None = None
    title: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "StartChatForm":
        p = RequestDataParser
        return cls(
            persona_id=p.to_opt_int(form_data, "persona_id") or 0,
            worldinfo_id=p.to_opt_int(form_data, "worldinfo_id"),
            title=p.to_str(form_data, "title"),
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
