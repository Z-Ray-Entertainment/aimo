from dataclasses import dataclass, field

from shared.request_parsers import RequestDataParser


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
        p = RequestDataParser
        return cls(
            name=p.to_str(form_data, "name"),
            gender=p.to_str(form_data, "gender", "female"),
            visibility=p.to_str(form_data, "visibility", "private"),
            description=p.to_str(form_data, "description"),
            dialogue_examples_text=p.to_str(form_data, "dialogue_examples"),
            first_message=p.to_str(form_data, "first_message"),
            suggested_worldinfo_id=p.to_opt_int(form_data, "suggested_worldinfo_id"),
            initial_location_id=p.to_opt_int(form_data, "initial_location_id"),
            initial_relationship=p.to_int(form_data, "initial_relationship", default=0, min_val=-100, max_val=100),
            linked_lorebook_ids=p.to_int_list(form_data, "linked_lorebook_ids"),
            preferred_location_ids=p.to_int_list(form_data, "preferred_location_ids"),
            disliked_location_ids=p.to_int_list(form_data, "disliked_location_ids"),
        )
