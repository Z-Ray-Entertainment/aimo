from dataclasses import dataclass, field


@dataclass
class CharacterForm:
    name: str = ""
    gender: str = "female"
    visibility: str = "private"
    description: str = ""
    dialogue_examples_text: str = ""
    first_message: str = ""
    suggested_worldinfo_id: int | None = None
    initial_location_id: int | None = None
    initial_relationship: int = 0
    linked_lorebook_ids: list[int] = field(default_factory=list)
    preferred_location_ids: list[int] = field(default_factory=list)
    disliked_location_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_request(cls, form_data) -> "CharacterForm":
        def _opt_int(val) -> int | None:
            if val in (None, "", "0", 0):
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def _int_list(key: str) -> list[int]:
            raw_list = form_data.getlist(key) if hasattr(form_data, "getlist") else []
            out = []
            for x in raw_list:
                try:
                    out.append(int(x))
                except (ValueError, TypeError):
                    pass
            return out

        try:
            init_rel = int(form_data.get("initial_relationship", 0))
        except (ValueError, TypeError):
            init_rel = 0

        return cls(
            name=str(form_data.get("name", "")).strip(),
            gender=str(form_data.get("gender", "female")).strip(),
            visibility=str(form_data.get("visibility", "private")).strip(),
            description=str(form_data.get("description", "")).strip(),
            dialogue_examples_text=str(form_data.get("dialogue_examples", "")).strip(),
            first_message=str(form_data.get("first_message", "")).strip(),
            suggested_worldinfo_id=_opt_int(form_data.get("suggested_worldinfo_id")),
            initial_location_id=_opt_int(form_data.get("initial_location_id")),
            initial_relationship=max(-100, min(100, init_rel)),
            linked_lorebook_ids=_int_list("linked_lorebook_ids"),
            preferred_location_ids=_int_list("preferred_location_ids"),
            disliked_location_ids=_int_list("disliked_location_ids"),
        )
