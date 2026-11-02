import json
import sqlite3

from domain.characters.models import (
    Character,
    CharacterImage,
    Emotion,
    EmotionalSprite,
    Gender,
)
from infrastructure.database import get_db_session
from infrastructure.repositories.base import BaseRepository
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class CharacterRepository(BaseRepository[Character]):
    def list_visible(self, user_id: int) -> list[Character]:
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM characters
                WHERE visibility = 'public' OR user_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            ).fetchall()
            return [self._to_entity(conn, row) for row in rows]

    def get_by_id(self, character_id: int) -> Character | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM characters WHERE id = ?",
                (character_id,),
            ).fetchone()
            if row is None:
                return None
            return self._to_entity(conn, row)

    def save(self, character: Character) -> Character:
        created_str = format_datetime(character.created_at)
        with get_db_session() as conn:
            if character.id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO characters (
                        user_id, name, gender, visibility, primary_portrait_path,
                        avatar_path, card_image_path, appearance, description, dialogue_examples_json, linked_lorebook_ids_json,
                        lorebook_world_conditions_json, suggested_worldinfo_id, first_message, initial_location_id,
                        initial_relationship, preferred_location_ids_json,
                        disliked_location_ids_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        character.user_id,
                        character.name,
                        character.gender.value,
                        character.visibility,
                        character.primary_portrait_path,
                        character.avatar_path,
                        character.card_image_path,
                        getattr(character, "appearance", "") or "",
                        character.description,
                        json.dumps(character.dialogue_examples),
                        json.dumps(character.linked_lorebook_ids),
                        json.dumps(getattr(character, "lorebook_world_conditions", {}) or {}),
                        character.suggested_worldinfo_id,
                        character.first_message,
                        character.initial_location_id,
                        character.initial_relationship,
                        json.dumps(character.preferred_location_ids),
                        json.dumps(character.disliked_location_ids),
                        created_str,
                    ),
                )
                character.id = int(cursor.lastrowid or 0)
            else:
                existing = conn.execute(
                    "SELECT id FROM characters WHERE id = ?",
                    (character.id,),
                ).fetchone()
                if existing is None:
                    character.id = None
                    return self.save(character)
                conn.execute(
                    """
                    UPDATE characters
                    SET name = ?, gender = ?, visibility = ?, primary_portrait_path = ?,
                        avatar_path = ?, card_image_path = ?, appearance = ?, description = ?, dialogue_examples_json = ?, linked_lorebook_ids_json = ?,
                        lorebook_world_conditions_json = ?, suggested_worldinfo_id = ?, first_message = ?, initial_location_id = ?,
                        initial_relationship = ?, preferred_location_ids_json = ?,
                        disliked_location_ids_json = ?
                    WHERE id = ?
                    """,
                    (
                        character.name,
                        character.gender.value,
                        character.visibility,
                        character.primary_portrait_path,
                        character.avatar_path,
                        character.card_image_path,
                        getattr(character, "appearance", "") or "",
                        character.description,
                        json.dumps(character.dialogue_examples),
                        json.dumps(character.linked_lorebook_ids),
                        json.dumps(getattr(character, "lorebook_world_conditions", {}) or {}),
                        character.suggested_worldinfo_id,
                        character.first_message,
                        character.initial_location_id,
                        character.initial_relationship,
                        json.dumps(character.preferred_location_ids),
                        json.dumps(character.disliked_location_ids),
                        character.id,
                    ),
                )
            row = conn.execute(
                "SELECT * FROM characters WHERE id = ?",
                (character.id,),
            ).fetchone()
            return self._to_entity(conn, row)

    def delete(self, character_id: int) -> bool:
        return self._delete_by_id("characters", character_id)

    def add_sprite(self, character_id: int, sprite: EmotionalSprite) -> EmotionalSprite:
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO character_sprites (character_id, emotion, variant, file_path)
                VALUES (?, ?, ?, ?)
                """,
                (
                    character_id,
                    sprite.emotion.value,
                    sprite.variant,
                    sprite.file_path,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            return EmotionalSprite(
                id=new_id,
                character_id=character_id,
                emotion=sprite.emotion,
                variant=sprite.variant,
                file_path=sprite.file_path,
            )

    def delete_sprite(self, character_id: int, emotion: str, variant: int) -> bool:
        resolved_emotion = Emotion.resolve(emotion).value
        with get_db_session() as conn:
            row = conn.execute(
                """
                SELECT id FROM character_sprites
                WHERE character_id = ? AND emotion = ? AND variant = ?
                """,
                (character_id, resolved_emotion, variant),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "DELETE FROM character_sprites WHERE id = ?",
                (int(row["id"]),),
            )
            return True

    def add_gallery_image(self, character_id: int, image: CharacterImage) -> CharacterImage:
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO character_images (character_id, file_path, unlock_threshold)
                VALUES (?, ?, ?)
                """,
                (
                    character_id,
                    image.file_path,
                    image.unlock_threshold,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            return CharacterImage(
                id=new_id,
                character_id=character_id,
                file_path=image.file_path,
                unlock_threshold=image.unlock_threshold,
            )

    def update_gallery_image_threshold(self, image_id: int, threshold: int) -> bool:
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM character_images WHERE id = ?",
                (image_id,),
            ).fetchone()
            if existing is None:
                return False
            clamped = max(-100, min(100, int(threshold)))
            conn.execute(
                "UPDATE character_images SET unlock_threshold = ? WHERE id = ?",
                (clamped, image_id),
            )
            return True

    def delete_gallery_image(self, image_id: int) -> bool:
        return self._delete_by_id("character_images", image_id)

    def get_best_relationship_for_user(
        self,
        character_id: int,
        user_id: int,
        default_value: float = 0.0,
    ) -> float:
        with get_db_session() as conn:
            row = conn.execute(
                """
                SELECT MAX(relationship_value) AS best
                FROM chat_sessions
                WHERE character_id = ? AND user_id = ?
                """,
                (character_id, user_id),
            ).fetchone()
            if row is None or row["best"] is None:
                return float(default_value)
            return float(row["best"])

    def get_message_count_for_user(self, character_id: int, user_id: int) -> int:
        with get_db_session() as conn:
            row = conn.execute(
                """
                SELECT COUNT(m.id) AS cnt
                FROM chat_messages m
                JOIN chat_sessions s ON m.session_id = s.id
                WHERE s.character_id = ? AND s.user_id = ?
                """,
                (character_id, user_id),
            ).fetchone()
            return int(row["cnt"] if row is not None and row["cnt"] is not None else 0)

    @staticmethod
    def _to_entity(conn: sqlite3.Connection, row: sqlite3.Row) -> Character:
        def _load_list(raw: str) -> list:
            try:
                val = json.loads(raw)
                return list(val) if isinstance(val, list) else []
            except json.JSONDecodeError:
                return []

        def _load_dict(raw: str) -> dict[int, int]:
            try:
                val = json.loads(raw)
                if isinstance(val, dict):
                    return {int(k): int(v) for k, v in val.items() if str(k).isdigit() and str(v).isdigit()}
                return {}
            except (json.JSONDecodeError, ValueError):
                return {}

        char_id = int(row["id"])
        img_rows = conn.execute(
            "SELECT * FROM character_images WHERE character_id = ? ORDER BY id ASC",
            (char_id,),
        ).fetchall()
        gallery = [
            CharacterImage(
                id=int(img["id"]),
                character_id=int(img["character_id"]),
                file_path=str(img["file_path"]),
                unlock_threshold=int(img["unlock_threshold"]),
            )
            for img in img_rows
        ]

        sprite_rows = conn.execute(
            "SELECT * FROM character_sprites WHERE character_id = ? ORDER BY id ASC",
            (char_id,),
        ).fetchall()
        sprites = [
            EmotionalSprite(
                id=int(sp["id"]),
                character_id=int(sp["character_id"]),
                emotion=Emotion.resolve(str(sp["emotion"])),
                variant=int(sp["variant"]),
                file_path=str(sp["file_path"]),
            )
            for sp in sprite_rows
        ]

        return Character(
            id=char_id,
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            gender=Gender.resolve(str(row["gender"])),
            visibility=str(row["visibility"]),
            primary_portrait_path=str(row["primary_portrait_path"]),
            avatar_path=(
                str(row["avatar_path"])
                if ("avatar_path" in row.keys() and row["avatar_path"])
                else None
            ),
            card_image_path=(
                str(row["card_image_path"])
                if ("card_image_path" in row.keys() and row["card_image_path"])
                else None
            ),
            appearance=(
                str(row["appearance"])
                if ("appearance" in row.keys() and row["appearance"])
                else ""
            ),
            description=str(row["description"]),
            dialogue_examples=[
                (
                    {
                        "trigger": str(x.get("trigger", "")),
                        "response": str(x.get("response", "")),
                    }
                    if isinstance(x, dict)
                    else {"trigger": "", "response": str(x)}
                )
                for x in _load_list(str(row["dialogue_examples_json"]))
            ],
            linked_lorebook_ids=[int(x) for x in _load_list(str(row["linked_lorebook_ids_json"]))],
            lorebook_world_conditions=_load_dict(str(row["lorebook_world_conditions_json"])) if "lorebook_world_conditions_json" in row.keys() and row["lorebook_world_conditions_json"] else {},
            suggested_worldinfo_id=(
                int(row["suggested_worldinfo_id"])
                if row["suggested_worldinfo_id"] is not None
                else None
            ),
            first_message=str(row["first_message"]),
            initial_location_id=(
                int(row["initial_location_id"])
                if row["initial_location_id"] is not None
                else None
            ),
            initial_relationship=int(row["initial_relationship"]),
            preferred_location_ids=[
                int(x) for x in _load_list(str(row["preferred_location_ids_json"]))
            ],
            disliked_location_ids=[
                int(x) for x in _load_list(str(row["disliked_location_ids_json"]))
            ],
            gallery_images=gallery,
            sprites=sprites,
            created_at=parse_datetime(row["created_at"]),
        )
