from datetime import datetime, timezone
import json
import random
import re
from typing import Any

from domain.validation import DomainValidator
from domain.worldinfo.exceptions import InvalidWorldInfoDataError
from domain.worldinfo.models import Event, EventCooldownState, Location, WorldInfo
from shared.utils import parse_tags


class WorldInfoService:
    def create_worldinfo(
        self,
        user_id: int,
        name: str,
        icon: str | None = "🌐",
        visibility: str = "private",
        cover_image_path: str | None = None,
        lorebook_id: int | None = None,
        collaborator_creator_tags: list[str] | None = None,
    ) -> WorldInfo:
        DomainValidator.validate_positive_user_id(user_id, InvalidWorldInfoDataError)
        cleaned_name = DomainValidator.validate_required_string(name, "WorldInfo name", InvalidWorldInfoDataError)
        cleaned_icon = icon.strip() if isinstance(icon, str) and icon.strip() else "🌐"
        cleaned_vis = DomainValidator.normalize_visibility(visibility)
        cleaned_cover = cover_image_path.strip() if isinstance(cover_image_path, str) and cover_image_path.strip() else None
        valid_lb_id = int(lorebook_id) if lorebook_id is not None and int(lorebook_id) > 0 else None

        return WorldInfo(
            id=None,
            user_id=user_id,
            name=cleaned_name,
            icon=cleaned_icon,
            visibility=cleaned_vis,
            cover_image_path=cleaned_cover,
            lorebook_id=valid_lb_id,
            collaborator_creator_tags=[
                t.strip().lower() for t in collaborator_creator_tags
                if isinstance(t, str) and t.strip()
            ] if collaborator_creator_tags else [],
            created_at=datetime.now(timezone.utc),
        )

    def update_worldinfo(
        self,
        worldinfo: WorldInfo,
        name: str,
        icon: str | None | object = ...,
        visibility: str | None = None,
        cover_image_path: str | None | object = ...,
        lorebook_id: int | None | object = ...,
        collaborator_creator_tags: list[str] | None = None,
    ) -> WorldInfo:
        worldinfo.name = DomainValidator.validate_required_string(name, "WorldInfo name", InvalidWorldInfoDataError)
        if icon is not ...:
            worldinfo.icon = icon.strip() if isinstance(icon, str) and icon.strip() else (worldinfo.icon or "🌐")
        if visibility is not None:
            worldinfo.visibility = DomainValidator.normalize_visibility(visibility)
        if cover_image_path is not ...:
            worldinfo.cover_image_path = (
                cover_image_path.strip()
                if isinstance(cover_image_path, str) and cover_image_path.strip()
                else None
            )
        if lorebook_id is not ...:
            worldinfo.lorebook_id = int(lorebook_id) if lorebook_id is not None and int(lorebook_id) > 0 else None
        if collaborator_creator_tags is not None:
            worldinfo.collaborator_creator_tags = [
                t.strip().lower() for t in collaborator_creator_tags
                if isinstance(t, str) and t.strip()
            ]
        return worldinfo

    def extract_tags_from_description(
        self,
        description: str,
        llm_provider: Any,
        model: str,
    ) -> list[str]:
        cleaned_desc = description.strip()
        if not cleaned_desc:
            return []

        prompt = (
            "Analyze the following location description for a roleplay setting.\n"
            "Extract 3 to 8 concise, relevant keyword tags characterizing the environment, "
            "architecture, mood, lighting, and setting (e.g. tavern, forest, cozy, dark, quiet).\n"
            "Return strictly a comma-separated list or JSON array of lowercase tags without extra explanation.\n\n"
            f"Description:\n{cleaned_desc}"
        )
        try:
            raw_output = llm_provider.generate(
                prompt=prompt,
                model=model,
            ).strip()
        except Exception:
            return []

        cleaned_output = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()
        if not cleaned_output and raw_output:
            cleaned_output = re.sub(r"<think>.*", "", raw_output, flags=re.DOTALL).strip() or raw_output
        cleaned_output = re.sub(r"^```(?:json)?\s*", "", cleaned_output, flags=re.MULTILINE)
        cleaned_output = re.sub(r"\s*```$", "", cleaned_output, flags=re.MULTILINE).strip()

        json_match = re.search(r"\[.*\]", cleaned_output, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, list):
                    return parse_tags(parsed)
            except json.JSONDecodeError:
                pass

        return parse_tags(cleaned_output)

    def add_location(
        self,
        worldinfo_id: int,
        name: str,
        tags: list[str] | str,
        description: str,
        bg_path: str | None = None,
        vision_alt_text: str | None = None,
        character_id: int | None = None,
    ) -> Location:
        if isinstance(worldinfo_id, bool) or not isinstance(worldinfo_id, int) or worldinfo_id <= 0:
            raise InvalidWorldInfoDataError("A valid positive worldinfo_id is required.")

        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidWorldInfoDataError("Location name must not be empty.")

        normalized_tags = parse_tags(tags)
        cleaned_desc = description.strip() if isinstance(description, str) else ""
        cleaned_bg = bg_path.strip() if isinstance(bg_path, str) and bg_path.strip() else None
        cleaned_alt = (
            vision_alt_text.strip()
            if isinstance(vision_alt_text, str) and vision_alt_text.strip()
            else None
        )
        valid_char_id = (
            int(character_id)
            if character_id is not None and not isinstance(character_id, bool) and int(character_id) > 0
            else None
        )

        return Location(
            id=None,
            worldinfo_id=worldinfo_id,
            name=cleaned_name,
            tags=normalized_tags,
            description=cleaned_desc,
            background_image_path=cleaned_bg,
            vision_alt_text=cleaned_alt,
            character_id=valid_char_id,
        )

    def update_location(
        self,
        location: Location,
        name: str,
        tags: list[str] | str,
        description: str,
        bg_path: str | None = None,
        vision_alt_text: str | None = None,
        character_id: int | None | object = ...,
    ) -> Location:
        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidWorldInfoDataError("Location name must not be empty.")

        location.name = cleaned_name
        location.tags = parse_tags(tags)
        location.description = description.strip() if isinstance(description, str) else ""
        if bg_path is not None:
            location.background_image_path = bg_path.strip() if bg_path.strip() else None
        if vision_alt_text is not None:
            location.vision_alt_text = vision_alt_text.strip() if vision_alt_text.strip() else None
        if character_id is not ...:
            location.character_id = (
                int(character_id)
                if character_id is not None and not isinstance(character_id, bool) and int(character_id) > 0
                else None
            )
        return location

    def add_event(
        self,
        worldinfo_id: int,
        title: str,
        description: str,
        probability: int,
        one_shot: bool = False,
        location_id: int | None = None,
    ) -> Event:
        if isinstance(worldinfo_id, bool) or not isinstance(worldinfo_id, int) or worldinfo_id <= 0:
            raise InvalidWorldInfoDataError("A valid positive worldinfo_id is required.")

        cleaned_title = title.strip() if isinstance(title, str) else ""
        if not cleaned_title:
            raise InvalidWorldInfoDataError("Event title must not be empty.")

        cleaned_desc = description.strip() if isinstance(description, str) else ""
        if not cleaned_desc:
            raise InvalidWorldInfoDataError("Event description must not be empty.")

        if isinstance(probability, bool) or not isinstance(probability, int) or not (0 <= probability <= 100):
            raise InvalidWorldInfoDataError("Event probability must be an integer between 0 and 100.")

        if location_id is not None and (isinstance(location_id, bool) or not isinstance(location_id, int) or location_id <= 0):
            raise InvalidWorldInfoDataError("location_id must be None (World Event) or a positive integer.")

        return Event(
            id=None,
            worldinfo_id=worldinfo_id,
            location_id=location_id,
            title=cleaned_title,
            probability=probability,
            one_shot=bool(one_shot),
            description=cleaned_desc,
        )

    def update_event(
        self,
        event: Event,
        title: str,
        description: str,
        probability: int,
        one_shot: bool = False,
        location_id: int | None = None,
    ) -> Event:
        cleaned_title = title.strip() if isinstance(title, str) else ""
        if not cleaned_title:
            raise InvalidWorldInfoDataError("Event title must not be empty.")

        cleaned_desc = description.strip() if isinstance(description, str) else ""
        if not cleaned_desc:
            raise InvalidWorldInfoDataError("Event description must not be empty.")

        if isinstance(probability, bool) or not isinstance(probability, int) or not (0 <= probability <= 100):
            raise InvalidWorldInfoDataError("Event probability must be an integer between 0 and 100.")

        event.title = cleaned_title
        event.description = cleaned_desc
        event.probability = probability
        event.one_shot = bool(one_shot)
        event.location_id = location_id
        return event

    def initialize_cooldown(self) -> int:
        return random.randint(10, 100)

    def decrement_cooldown(self, state: EventCooldownState) -> bool:
        state.current_counter -= 1
        return state.current_counter <= 0

    def draw_event(
        self,
        worldinfo_events: list[Event],
        current_location_id: int | None,
        state: EventCooldownState,
    ) -> Event | None:
        state.current_counter = self.initialize_cooldown()

        pool = [
            ev
            for ev in worldinfo_events
            if (ev.location_id is None or ev.location_id == current_location_id)
            and ev.probability > 0
            and not (ev.one_shot and ev.id is not None and ev.id in state.triggered_event_ids)
        ]

        if not pool:
            return None

        weights = [ev.probability for ev in pool]
        chosen_event = random.choices(pool, weights=weights, k=1)[0]

        if chosen_event.one_shot and chosen_event.id is not None:
            state.triggered_event_ids.add(chosen_event.id)

        return chosen_event
