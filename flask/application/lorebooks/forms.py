from dataclasses import dataclass

from shared.request_parsers import RequestDataParser


@dataclass
class LorebookEntryForm:
    title: str = ""
    tags: str = ""
    content: str = ""

    @classmethod
    def from_request(cls, form_data) -> "LorebookEntryForm":
        p = RequestDataParser
        return cls(
            title=p.to_str(form_data, "title"),
            tags=p.to_str(form_data, "tags"),
            content=p.to_str(form_data, "content"),
        )
