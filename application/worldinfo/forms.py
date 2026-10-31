from dataclasses import dataclass


@dataclass
class LocationForm:
    name: str = ""
    tags: str = ""
    description: str = ""
    background_image_path: str = ""
    vision_alt_text: str = ""

    @classmethod
    def from_request(cls, form_data: dict) -> "LocationForm":
        return cls(
            name=str(form_data.get("name", "")).strip(),
            tags=str(form_data.get("tags", "")).strip(),
            description=str(form_data.get("description", "")).strip(),
            background_image_path=str(form_data.get("background_image_path", "")).strip(),
            vision_alt_text=str(form_data.get("vision_alt_text", "")).strip(),
        )


@dataclass
class EventForm:
    title: str = ""
    probability: int = 50
    one_shot: bool = False
    location_id: int | None = None
    description: str = ""

    @classmethod
    def from_request(cls, form_data: dict) -> "EventForm":
        loc_raw = form_data.get("location_id")
        loc_id = None
        if loc_raw not in (None, "", "world", "0", 0):
            try:
                loc_id = int(loc_raw)
            except (ValueError, TypeError):
                loc_id = None
        try:
            prob = int(form_data.get("probability", 50))
        except (ValueError, TypeError):
            prob = 50
        return cls(
            title=str(form_data.get("title", "")).strip(),
            probability=max(0, min(100, prob)),
            one_shot=bool(form_data.get("one_shot")),
            location_id=loc_id,
            description=str(form_data.get("description", "")).strip(),
        )
