from dataclasses import dataclass

from security import RequestDataParser


@dataclass
class LorebookForm:
    name: str = ""
    description: str = ""
    visibility: str = "private"
    is_proper_noun: bool = False

    @classmethod
    def from_request(cls, form_data) -> "LorebookForm":
        p = RequestDataParser
        return cls(
            name=p.to_str(form_data, "name"),
            description=p.to_str(form_data, "description"),
            visibility=p.to_str(form_data, "visibility", "private"),
            is_proper_noun=p.to_bool(form_data, "is_proper_noun"),
        )


@dataclass
class LorebookEntryForm:
    title: str = ""
    tags: str = ""
    content: str = ""
    visibility: str = "public"
    is_proper_noun: bool = False

    @classmethod
    def from_request(cls, form_data) -> "LorebookEntryForm":
        p = RequestDataParser
        return cls(
            title=p.to_str(form_data, "title"),
            tags=p.to_str(form_data, "tags"),
            content=p.to_str(form_data, "content"),
            visibility=p.to_str(form_data, "visibility", "public"),
            is_proper_noun=p.to_bool(form_data, "is_proper_noun"),
        )
