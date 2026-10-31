import json

from sqlalchemy import func, or_, select

from domain.characters.models import (
    Character,
    CharacterImage,
    Emotion,
    EmotionalSprite,
    Gender,
)
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import (
    CharacterImageORM,
    CharacterORM,
    ChatSessionORM,
    MessageORM,
    SpriteORM,
)


class CharacterRepository:
    def list_visible(self, user_id: int) -> list[Character]:
        with get_db_session() as session:
            stmt = (
                select(CharacterORM)
                .where(
                    or_(
                        CharacterORM.visibility == "public",
                        CharacterORM.user_id == user_id,
                    )
                )
                .order_by(CharacterORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, character_id: int) -> Character | None:
        with get_db_session() as session:
            orm_char = session.get(CharacterORM, character_id)
            if orm_char is None:
                return None
            return self._to_entity(orm_char)

    def save(self, character: Character) -> Character:
        with get_db_session() as session:
            if character.id is None:
                orm_char = CharacterORM(
                    user_id=character.user_id,
                    name=character.name,
                    gender=character.gender.value,
                    visibility=character.visibility,
                    primary_portrait_path=character.primary_portrait_path,
                    description=character.description,
                    dialogue_examples_json=json.dumps(character.dialogue_examples),
                    linked_lorebook_ids_json=json.dumps(character.linked_lorebook_ids),
                    suggested_worldinfo_id=character.suggested_worldinfo_id,
                    first_message=character.first_message,
                    initial_location_id=character.initial_location_id,
                    initial_relationship=character.initial_relationship,
                    preferred_location_ids_json=json.dumps(character.preferred_location_ids),
                    disliked_location_ids_json=json.dumps(character.disliked_location_ids),
                    created_at=character.created_at,
                )
                session.add(orm_char)
                session.flush()
                character.id = orm_char.id
            else:
                orm_char = session.get(CharacterORM, character.id)
                if orm_char is None:
                    character.id = None
                    return self.save(character)
                orm_char.name = character.name
                orm_char.gender = character.gender.value
                orm_char.visibility = character.visibility
                orm_char.primary_portrait_path = character.primary_portrait_path
                orm_char.description = character.description
                orm_char.dialogue_examples_json = json.dumps(character.dialogue_examples)
                orm_char.linked_lorebook_ids_json = json.dumps(character.linked_lorebook_ids)
                orm_char.suggested_worldinfo_id = character.suggested_worldinfo_id
                orm_char.first_message = character.first_message
                orm_char.initial_location_id = character.initial_location_id
                orm_char.initial_relationship = character.initial_relationship
                orm_char.preferred_location_ids_json = json.dumps(character.preferred_location_ids)
                orm_char.disliked_location_ids_json = json.dumps(character.disliked_location_ids)
                session.flush()

            return self._to_entity(orm_char)

    def delete(self, character_id: int) -> bool:
        with get_db_session() as session:
            orm_char = session.get(CharacterORM, character_id)
            if orm_char is None:
                return False
            session.delete(orm_char)
            return True

    def add_sprite(self, character_id: int, sprite: EmotionalSprite) -> EmotionalSprite:
        with get_db_session() as session:
            orm_sprite = SpriteORM(
                character_id=character_id,
                emotion=sprite.emotion.value,
                variant=sprite.variant,
                file_path=sprite.file_path,
            )
            session.add(orm_sprite)
            session.flush()
            return EmotionalSprite(
                id=orm_sprite.id,
                character_id=orm_sprite.character_id,
                emotion=Emotion.resolve(orm_sprite.emotion),
                variant=orm_sprite.variant,
                file_path=orm_sprite.file_path,
            )

    def delete_sprite(self, character_id: int, emotion: str, variant: int) -> bool:
        resolved_emotion = Emotion.resolve(emotion).value
        with get_db_session() as session:
            stmt = select(SpriteORM).where(
                SpriteORM.character_id == character_id,
                SpriteORM.emotion == resolved_emotion,
                SpriteORM.variant == variant,
            )
            orm_sprite = session.execute(stmt).scalar_one_or_none()
            if orm_sprite is None:
                return False
            session.delete(orm_sprite)
            return True

    def add_gallery_image(self, character_id: int, image: CharacterImage) -> CharacterImage:
        with get_db_session() as session:
            orm_img = CharacterImageORM(
                character_id=character_id,
                file_path=image.file_path,
                unlock_threshold=image.unlock_threshold,
            )
            session.add(orm_img)
            session.flush()
            return CharacterImage(
                id=orm_img.id,
                character_id=orm_img.character_id,
                file_path=orm_img.file_path,
                unlock_threshold=orm_img.unlock_threshold,
            )

    def update_gallery_image_threshold(self, image_id: int, threshold: int) -> bool:
        with get_db_session() as session:
            orm_img = session.get(CharacterImageORM, image_id)
            if orm_img is None:
                return False
            orm_img.unlock_threshold = max(-100, min(100, int(threshold)))
            return True

    def delete_gallery_image(self, image_id: int) -> bool:
        with get_db_session() as session:
            orm_img = session.get(CharacterImageORM, image_id)
            if orm_img is None:
                return False
            session.delete(orm_img)
            return True

    def get_best_relationship_for_user(
        self,
        character_id: int,
        user_id: int,
        default_value: float = 0.0,
    ) -> float:
        with get_db_session() as session:
            stmt = (
                select(func.max(ChatSessionORM.relationship_value))
                .where(
                    ChatSessionORM.character_id == character_id,
                    ChatSessionORM.user_id == user_id,
                )
            )
            best = session.execute(stmt).scalar_one_or_none()
            if best is None:
                return float(default_value)
            return float(best)

    def get_message_count_for_user(self, character_id: int, user_id: int) -> int:
        with get_db_session() as session:
            stmt = (
                select(func.count(MessageORM.id))
                .join(ChatSessionORM, MessageORM.session_id == ChatSessionORM.id)
                .where(
                    ChatSessionORM.character_id == character_id,
                    ChatSessionORM.user_id == user_id,
                )
            )
            count = session.execute(stmt).scalar_one_or_none()
            return int(count or 0)

    @staticmethod
    def _to_entity(orm_char: CharacterORM) -> Character:
        def _load_list(raw: str) -> list:
            try:
                val = json.loads(raw)
                return list(val) if isinstance(val, list) else []
            except json.JSONDecodeError:
                return []

        gallery = [
            CharacterImage(
                id=img.id,
                character_id=img.character_id,
                file_path=img.file_path,
                unlock_threshold=img.unlock_threshold,
            )
            for img in orm_char.gallery_images
        ]
        sprites = [
            EmotionalSprite(
                id=sp.id,
                character_id=sp.character_id,
                emotion=Emotion.resolve(sp.emotion),
                variant=sp.variant,
                file_path=sp.file_path,
            )
            for sp in orm_char.sprites
        ]

        return Character(
            id=orm_char.id,
            user_id=orm_char.user_id,
            name=orm_char.name,
            gender=Gender.resolve(orm_char.gender),
            visibility=orm_char.visibility,
            primary_portrait_path=orm_char.primary_portrait_path,
            description=orm_char.description,
            dialogue_examples=[str(x) for x in _load_list(orm_char.dialogue_examples_json)],
            linked_lorebook_ids=[int(x) for x in _load_list(orm_char.linked_lorebook_ids_json)],
            suggested_worldinfo_id=orm_char.suggested_worldinfo_id,
            first_message=orm_char.first_message,
            initial_location_id=orm_char.initial_location_id,
            initial_relationship=orm_char.initial_relationship,
            preferred_location_ids=[int(x) for x in _load_list(orm_char.preferred_location_ids_json)],
            disliked_location_ids=[int(x) for x in _load_list(orm_char.disliked_location_ids_json)],
            gallery_images=gallery,
            sprites=sprites,
            created_at=orm_char.created_at,
        )
