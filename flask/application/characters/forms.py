from dataclasses import dataclass, field
import json

from shared.request_parsers import RequestDataParser


@dataclass
class CharacterForm:
    name: str = ""
    gender: str = "female"
    visibility: str = "private"
    appearance: str = ""
    description: str = ""
    dialogue_examples_text: str = ""
    dialogue_examples: list[dict[str, str]] = field(default_factory=list)
    first_message: str = ""
    suggested_worldinfo_id: int | None = None
    initial_location_id: int | None = None
    initial_relationship: int = 0
    linked_lorebook_ids: list[int] = field(default_factory=list)
    lorebook_world_conditions: dict[int, int] = field(default_factory=dict)
    preferred_location_ids: list[int] = field(default_factory=list)
    disliked_location_ids: list[int] = field(default_factory=list)
    collaborator_creator_tags: list[str] = field(default_factory=list)
    collaborator_creator_tags_text: str = ""

    @classmethod
    def from_request(cls, form_data) -> "CharacterForm":
        p = RequestDataParser
        examples_json_str = p.to_str(form_data, "dialogue_examples_json")
        dialogue_examples: list[dict[str, str]] = []
        if examples_json_str:
            try:
                parsed = json.loads(examples_json_str)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            t = str(item.get("trigger", "")).strip()
                            r = str(item.get("response", "")).strip()
                            if t or r:
                                dialogue_examples.append({"trigger": t, "response": r})
            except Exception:
                pass

        if not dialogue_examples:
            raw_text = p.to_str(form_data, "dialogue_examples")
            if raw_text:
                for line in raw_text.splitlines():
                    if line.strip():
                        dialogue_examples.append({"trigger": "", "response": line.strip()})

        lorebook_world_conditions: dict[int, int] = {}
        conditions_json = p.to_str(form_data, "lorebook_world_conditions_json")
        if conditions_json:
            try:
                raw_cond = json.loads(conditions_json)
                if isinstance(raw_cond, dict):
                    for k, v in raw_cond.items():
                        if str(k).isdigit() and str(v).isdigit() and int(v) > 0:
                            lorebook_world_conditions[int(k)] = int(v)
            except (json.JSONDecodeError, ValueError):
                pass

        items_dict = form_data.to_dict() if hasattr(form_data, "to_dict") else dict(form_data)
        for key, val in items_dict.items():
            if key.startswith("lorebook_world_condition_"):
                lb_id_str = key.replace("lorebook_world_condition_", "")
                if lb_id_str.isdigit() and str(val).isdigit() and int(val) > 0:
                    lorebook_world_conditions[int(lb_id_str)] = int(val)

        raw_tags = p.to_str(form_data, "collaborator_creator_tags")
        collaborator_tags = [
            t.strip().lower() for t in raw_tags.split(",")
            if t.strip()
        ]

        return cls(
            name=p.to_str(form_data, "name"),
            gender=p.to_str(form_data, "gender", "female"),
            visibility=p.to_str(form_data, "visibility", "private"),
            appearance=p.to_str(form_data, "appearance"),
            description=p.to_str(form_data, "description"),
            dialogue_examples_text=p.to_str(form_data, "dialogue_examples"),
            dialogue_examples=dialogue_examples,
            first_message=p.to_str(form_data, "first_message"),
            suggested_worldinfo_id=p.to_opt_int(form_data, "suggested_worldinfo_id"),
            initial_location_id=p.to_opt_int(form_data, "initial_location_id"),
            initial_relationship=p.to_int(form_data, "initial_relationship", default=0, min_val=-100, max_val=100),
            linked_lorebook_ids=p.to_int_list(form_data, "linked_lorebook_ids"),
            lorebook_world_conditions=lorebook_world_conditions,
            preferred_location_ids=p.to_int_list(form_data, "preferred_location_ids"),
            disliked_location_ids=p.to_int_list(form_data, "disliked_location_ids"),
            collaborator_creator_tags=collaborator_tags,
            collaborator_creator_tags_text=raw_tags,
        )
