from datetime import datetime, timezone
import random

from domain.characters.exceptions import InvalidCharacterDataError
from domain.characters.models import (
    Character,
    CharacterImage,
    Emotion,
    EmotionalSprite,
    Gender,
)
from domain.validation import DomainValidator


class CharacterService:
    def create_character(
        self,
        user_id: int,
        name: str,
        gender: Gender | str,
        primary_portrait_path: str,
        description: str,
        first_message: str,
        visibility: str = "private",
        dialogue_examples: list | None = None,
        linked_lorebook_ids: list[int] | None = None,
        lorebook_world_conditions: dict[int, int] | None = None,
        suggested_worldinfo_id: int | None = None,
        initial_location_id: int | None = None,
        initial_relationship: int = 0,
        preferred_location_ids: list[int] | None = None,
        disliked_location_ids: list[int] | None = None,
        avatar_path: str | None = None,
        card_image_path: str | None = None,
        appearance: str = "",
        collaborator_creator_tags: list[str] | None = None,
    ) -> Character:
        DomainValidator.validate_positive_user_id(user_id, InvalidCharacterDataError)
        cleaned_name = DomainValidator.validate_required_string(name, "Character name", InvalidCharacterDataError)

        try:
            resolved_gender = Gender.resolve(gender)
        except ValueError as exc:
            raise InvalidCharacterDataError(str(exc)) from exc

        cleaned_portrait = DomainValidator.validate_required_string(primary_portrait_path, "primary_portrait_path", InvalidCharacterDataError)
        cleaned_desc = description.strip() if isinstance(description, str) else ""
        cleaned_first_msg = (
            first_message.strip() if isinstance(first_message, str) else ""
        )
        cleaned_appearance = appearance.strip() if isinstance(appearance, str) else ""

        cleaned_vis = visibility.strip().lower() if isinstance(visibility, str) else "private"
        if cleaned_vis not in ("private", "public"):
            raise InvalidCharacterDataError("Visibility must be 'private' or 'public'.")

        if isinstance(initial_relationship, bool) or not isinstance(initial_relationship, int) or not (-100 <= initial_relationship <= 100):
            raise InvalidCharacterDataError(
                "initial_relationship must be an integer between -100 and 100."
            )

        cleaned_avatar = avatar_path.strip() if isinstance(avatar_path, str) and avatar_path.strip() else None
        cleaned_card = card_image_path.strip() if isinstance(card_image_path, str) and card_image_path.strip() else None

        if suggested_worldinfo_id is None:
            initial_location_id = None
            preferred_location_ids = []
            disliked_location_ids = []

        return Character(
            id=None,
            user_id=user_id,
            name=cleaned_name,
            gender=resolved_gender,
            visibility=cleaned_vis,
            primary_portrait_path=cleaned_portrait,
            description=cleaned_desc,
            first_message=cleaned_first_msg,
            avatar_path=cleaned_avatar,
            card_image_path=cleaned_card,
            appearance=cleaned_appearance,
            collaborator_creator_tags=[
                t.strip().lower() for t in collaborator_creator_tags
                if isinstance(t, str) and t.strip()
            ] if collaborator_creator_tags else [],
            dialogue_examples=list(dialogue_examples or []),
            linked_lorebook_ids=list(linked_lorebook_ids or []),
            lorebook_world_conditions=dict(lorebook_world_conditions or {}),
            suggested_worldinfo_id=suggested_worldinfo_id,
            initial_location_id=initial_location_id,
            initial_relationship=initial_relationship,
            preferred_location_ids=list(preferred_location_ids or []),
            disliked_location_ids=list(disliked_location_ids or []),
            gallery_images=[],
            sprites=[],
            created_at=datetime.now(timezone.utc),
        )

    def update_character(
        self,
        character: Character,
        name: str,
        gender: Gender | str,
        primary_portrait_path: str,
        description: str,
        first_message: str,
        visibility: str = "private",
        dialogue_examples: list | None = None,
        linked_lorebook_ids: list[int] | None = None,
        lorebook_world_conditions: dict[int, int] | None = None,
        suggested_worldinfo_id: int | None = None,
        initial_location_id: int | None = None,
        initial_relationship: int = 0,
        preferred_location_ids: list[int] | None = None,
        disliked_location_ids: list[int] | None = None,
        avatar_path: str | None = None,
        card_image_path: str | None = None,
        appearance: str | None = None,
        collaborator_creator_tags: list[str] | None = None,
    ) -> Character:
        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidCharacterDataError("Character name must not be empty.")

        try:
            resolved_gender = Gender.resolve(gender)
        except ValueError as exc:
            raise InvalidCharacterDataError(str(exc)) from exc

        cleaned_portrait = (
            primary_portrait_path.strip()
            if isinstance(primary_portrait_path, str)
            else ""
        )
        if not cleaned_portrait:
            raise InvalidCharacterDataError("primary_portrait_path must not be empty.")

        cleaned_vis = visibility.strip().lower() if isinstance(visibility, str) else "private"
        if cleaned_vis not in ("private", "public"):
            raise InvalidCharacterDataError("Visibility must be 'private' or 'public'.")

        if isinstance(initial_relationship, bool) or not isinstance(initial_relationship, int) or not (-100 <= initial_relationship <= 100):
            raise InvalidCharacterDataError(
                "initial_relationship must be an integer between -100 and 100."
            )

        character.name = cleaned_name
        character.gender = resolved_gender
        character.primary_portrait_path = cleaned_portrait
        if avatar_path is not None:
            character.avatar_path = avatar_path.strip() if avatar_path.strip() else None
        if card_image_path is not None:
            character.card_image_path = card_image_path.strip() if card_image_path.strip() else None
        if appearance is not None:
            character.appearance = appearance.strip() if isinstance(appearance, str) else ""
        character.description = description.strip() if isinstance(description, str) else ""
        character.first_message = (
            first_message.strip() if isinstance(first_message, str) else ""
        )
        character.visibility = cleaned_vis
        if dialogue_examples is not None:
            character.dialogue_examples = list(dialogue_examples)
        if linked_lorebook_ids is not None:
            character.linked_lorebook_ids = list(linked_lorebook_ids)
        if lorebook_world_conditions is not None:
            character.lorebook_world_conditions = dict(lorebook_world_conditions)

        if suggested_worldinfo_id is None:
            character.suggested_worldinfo_id = None
            character.initial_location_id = None
            character.preferred_location_ids = []
            character.disliked_location_ids = []
        else:
            character.suggested_worldinfo_id = suggested_worldinfo_id
            character.initial_location_id = initial_location_id
            if preferred_location_ids is not None:
                character.preferred_location_ids = list(preferred_location_ids)
            if disliked_location_ids is not None:
                character.disliked_location_ids = list(disliked_location_ids)

        character.initial_relationship = initial_relationship
        if collaborator_creator_tags is not None:
            character.collaborator_creator_tags = [
                t.strip().lower() for t in collaborator_creator_tags
                if isinstance(t, str) and t.strip()
            ]
        return character

    def add_gallery_image(
        self,
        character: Character,
        file_path: str,
        threshold: int,
    ) -> CharacterImage:
        cleaned_path = file_path.strip() if isinstance(file_path, str) else ""
        if not cleaned_path:
            raise InvalidCharacterDataError("Gallery image file_path must not be empty.")

        if isinstance(threshold, bool) or not isinstance(threshold, int) or not (-100 <= threshold <= 100):
            raise InvalidCharacterDataError(
                "Gallery image unlock_threshold must be an integer between -100 and 100."
            )

        image = CharacterImage(
            id=None,
            character_id=character.id or 0,
            file_path=cleaned_path,
            unlock_threshold=threshold,
        )
        character.gallery_images.append(image)
        return image

    def add_sprite(
        self,
        character: Character,
        emotion: Emotion | str,
        file_path: str,
    ) -> EmotionalSprite:
        cleaned_path = file_path.strip() if isinstance(file_path, str) else ""
        if not cleaned_path:
            raise InvalidCharacterDataError("Sprite file_path must not be empty.")

        resolved_emotion = Emotion.resolve(emotion)
        existing_variants = [
            sp.variant for sp in character.sprites if sp.emotion == resolved_emotion
        ]
        next_variant = 1
        while next_variant in existing_variants:
            next_variant += 1

        sprite = EmotionalSprite(
            emotion=resolved_emotion,
            variant=next_variant,
            file_path=cleaned_path,
            character_id=character.id,
        )
        character.sprites.append(sprite)
        return sprite

    def delete_sprite(
        self,
        character: Character,
        emotion: Emotion | str,
        variant: int,
    ) -> None:
        resolved_emotion = Emotion.resolve(emotion)
        character.sprites = [
            sp
            for sp in character.sprites
            if not (sp.emotion == resolved_emotion and sp.variant == variant)
        ]

    def select_sprite_for_emotion(
        self,
        character: Character,
        detected_emotion: Emotion | str,
    ) -> EmotionalSprite:
        resolved_emotion = Emotion.resolve(detected_emotion)
        matching_sprites = [
            sp for sp in character.sprites if sp.emotion == resolved_emotion
        ]
        if matching_sprites:
            return random.choice(matching_sprites)

        neutral_sprites = [
            sp for sp in character.sprites if sp.emotion == Emotion.NEUTRAL
        ]
        if neutral_sprites:
            return random.choice(neutral_sprites)

        return EmotionalSprite(
            emotion=Emotion.NEUTRAL,
            variant=1,
            file_path=character.primary_portrait_path,
            character_id=character.id,
        )

    def get_unlocked_images(
        self,
        character: Character,
        relationship_value: float,
    ) -> list[CharacterImage]:
        return [
            img
            for img in character.gallery_images
            if relationship_value >= img.unlock_threshold
        ]
