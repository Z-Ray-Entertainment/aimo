from dataclasses import dataclass

from shared.request_parsers import RequestDataParser


@dataclass
class LocationForm:
    name: str = ""
    tags: str = ""
    description: str = ""
    background_image_path: str = ""
    vision_alt_text: str = ""
    character_id: int | None = None
    is_proper_noun: bool = False

    @classmethod
    def from_request(cls, form_data) -> "LocationForm":
        p = RequestDataParser
        return cls(
            name=p.to_str(form_data, "name"),
            tags=p.to_str(form_data, "tags"),
            description=p.to_str(form_data, "description"),
            background_image_path=p.to_str(form_data, "background_image_path"),
            vision_alt_text=p.to_str(form_data, "vision_alt_text"),
            character_id=p.to_opt_int(form_data, "character_id"),
            is_proper_noun=p.to_bool(form_data, "is_proper_noun"),
        )


def _parse_opt_rel_int(form_data, key: str) -> int | None:
    if not hasattr(form_data, "get"):
        return None
    raw = form_data.get(key)
    if raw in (None, "", "none"):
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


@dataclass
class EventForm:
    title: str = ""
    probability: int = 50
    one_shot: bool = False
    location_id: int | None = None
    description: str = ""
    min_relationship: int | None = None
    max_relationship: int | None = None
    is_proper_noun: bool = False

    @classmethod
    def from_request(cls, form_data) -> "EventForm":
        p = RequestDataParser
        return cls(
            title=p.to_str(form_data, "title"),
            probability=p.to_int(form_data, "probability", default=50, min_val=0, max_val=100),
            one_shot=p.to_bool(form_data, "one_shot"),
            location_id=p.to_opt_int(form_data, "location_id"),
            description=p.to_str(form_data, "description"),
            min_relationship=_parse_opt_rel_int(form_data, "min_relationship"),
            max_relationship=_parse_opt_rel_int(form_data, "max_relationship"),
            is_proper_noun=p.to_bool(form_data, "is_proper_noun"),
        )
