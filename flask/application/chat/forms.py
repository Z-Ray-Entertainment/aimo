from dataclasses import dataclass
from typing import Any


@dataclass
class StartChatForm:
    persona_id: int = 0
    worldinfo_id: int | None = None
    title: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "StartChatForm":
        def _opt_int(key: str) -> int | None:
            val = str(form_data.get(key, "")).strip()
            if not val or val == "none":
                return None
            try:
                return int(val)
            except ValueError:
                return None

        persona_id = _opt_int("persona_id") or 0
        worldinfo_id = _opt_int("worldinfo_id")
        title = str(form_data.get("title", "")).strip()
        return cls(
            persona_id=persona_id,
            worldinfo_id=worldinfo_id,
            title=title,
        )


@dataclass
class MemoryEditForm:
    title: str = ""
    tags: str = ""
    summary: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "MemoryEditForm":
        return cls(
            title=str(form_data.get("title", "")).strip(),
            tags=str(form_data.get("tags", "")).strip(),
            summary=str(form_data.get("summary", "")).strip(),
        )
