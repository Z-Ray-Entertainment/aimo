from dataclasses import dataclass


@dataclass
class LorebookEntryForm:
    title: str = ""
    tags: str = ""
    content: str = ""

    @classmethod
    def from_request(cls, form_data: dict) -> "LorebookEntryForm":
        return cls(
            title=str(form_data.get("title", "")).strip(),
            tags=str(form_data.get("tags", "")).strip(),
            content=str(form_data.get("content", "")).strip(),
        )
