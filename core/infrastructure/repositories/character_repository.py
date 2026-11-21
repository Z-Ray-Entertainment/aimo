import json
import sqlite3

from domain.characters.models import (
    Character,
    CharacterImage,
    Emotion,
    EmotionalSprite,
    Gender,
)
from infrastructure.database import format_datetime, get_db_session, parse_datetime
from infrastructure.repositories.base import CollaborativeRepository
from infrastructure.repositories.duplication import duplicate_character_entity


class CharacterRepository(CollaborativeRepository[Character]):
    def _rows_to_entities(
        self, conn: sqlite3.Connection, rows: list[sqlite3.Row]
    ) -> list[Character]:
        if not rows:
            return []
        char_ids = [int(r["id"]) for r in rows]
        placeholders = ",".join("?" for _ in char_ids)
        img_rows = conn.execute(
            f"SELECT * FROM character_images WHERE character_id IN ({placeholders}) ORDER BY id ASC",
            tuple(char_ids),
        ).fetchall()
        sprite_rows = conn.execute(
            f"SELECT * FROM character_sprites WHERE character_id IN ({placeholders}) ORDER BY id ASC",
            tuple(char_ids),
        ).fetchall()

        gallery_map: dict[int, list[CharacterImage]] = {cid: [] for cid in char_ids}
        for img in img_rows:
            cid = int(img["character_id"])
            gallery_map.setdefault(cid, []).append(
                CharacterImage(
                    id=int(img["id"]),
                    character_id=cid,
                    file_path=str(img["file_path"]),
                    unlock_threshold=int(img["unlock_threshold"]),
                )
            )

        sprite_map: dict[int, list[EmotionalSprite]] = {cid: [] for cid in char_ids}
        for sp in sprite_rows:
            cid = int(sp["character_id"])
            sprite_map.setdefault(cid, []).append(
                EmotionalSprite(
                    id=int(sp["id"]),
                    character_id=cid,
                    emotion=Emotion.resolve(str(sp["emotion"])),
                    variant=int(sp["variant"]),
                    file_path=str(sp["file_path"]),
                )
            )

        return [
            self._row_to_entity(row, gallery_map.get(int(row["id"]), []), sprite_map.get(int(row["id"]), []))
            for row in rows
        ]

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
            return self._rows_to_entities(conn, rows)

    def list_for_user_creations(
        self, user_id: int, creator_tag: str | None = None
    ) -> list[Character]:
        return self._list_creations("characters", user_id, creator_tag)

    def get_by_id(self, character_id: int) -> Character | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM characters WHERE id = ?",
                (character_id,),
            ).fetchone()
            if row is None:
                return None
            return self._rows_to_entities(conn, [row])[0]

    def save(self, character: Character) -> Character:
        created_str = format_datetime(character.created_at)
        with get_db_session() as conn:
            if character.id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO characters (
                        user_id, name, gender, visibility, origin_language, collaborator_creator_tags_json, primary_portrait_path,
                        avatar_path, card_image_path, appearance, description, dialogue_examples_json, linked_lorebook_ids_json,
                        lorebook_world_conditions_json, suggested_worldinfo_id, first_message, initial_location_id,
                        initial_relationship, preferred_location_ids_json,
                        disliked_location_ids_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        character.user_id,
                        character.name,
                        character.gender.value,
                        character.visibility,
                        character.origin_language or "en",
                        json.dumps(character.collaborator_creator_tags),
                        character.primary_portrait_path,
                        character.avatar_path,
                        character.card_image_path,
                        character.appearance or "",
                        character.description,
                        json.dumps(character.dialogue_examples),
                        json.dumps(character.linked_lorebook_ids),
                        json.dumps(character.lorebook_world_conditions),
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
                    SET name = ?, gender = ?, visibility = ?, origin_language = ?, collaborator_creator_tags_json = ?, primary_portrait_path = ?,
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
                        character.origin_language or "en",
                        json.dumps(character.collaborator_creator_tags),
                        character.primary_portrait_path,
                        character.avatar_path,
                        character.card_image_path,
                        character.appearance or "",
                        character.description,
                        json.dumps(character.dialogue_examples),
                        json.dumps(character.linked_lorebook_ids),
                        json.dumps(character.lorebook_world_conditions),
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
            return self._rows_to_entities(conn, [row])[0]

    def delete(self, character_id: int) -> bool:
        return self._delete_by_id("characters", character_id)

    def duplicate(self, character_id: int, target_user_id: int) -> Character:
        return duplicate_character_entity(self, character_id, target_user_id)

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

    def delete_sprites_by_emotion(self, character_id: int, emotion: str) -> bool:
        resolved_emotion = Emotion.resolve(emotion).value
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                DELETE FROM character_sprites
                WHERE character_id = ? AND emotion = ?
                """,
                (character_id, resolved_emotion),
            )
            return cursor.rowcount > 0

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

    def list_popularity_ordered_ids(self) -> list[tuple[int, int | None]]:
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.suggested_worldinfo_id,
                       COUNT(DISTINCT cs.id) AS session_cnt,
                       COUNT(cm.id) AS msg_cnt
                FROM characters c
                LEFT JOIN chat_sessions cs ON cs.character_id = c.id
                LEFT JOIN chat_messages cm ON cm.session_id = cs.id
                GROUP BY c.id
                ORDER BY session_cnt DESC, msg_cnt DESC, c.id ASC
                """
            ).fetchall()
            return [
                (
                    int(r["id"]),
                    int(r["suggested_worldinfo_id"]) if r["suggested_worldinfo_id"] is not None else None,
                )
                for r in rows
            ]

    @classmethod
    def _row_to_entity(
        cls,
        row: sqlite3.Row,
        gallery: list[CharacterImage],
        sprites: list[EmotionalSprite],
    ) -> Character:
        raw_conditions = cls._row_json_dict(row, "lorebook_world_conditions_json")
        world_conditions = {
            int(k): int(v)
            for k, v in raw_conditions.items()
            if str(k).isdigit() and str(v).isdigit()
        }
        return Character(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            gender=Gender.resolve(str(row["gender"])),
            visibility=str(row["visibility"]),
            origin_language=cls._row_str(row, "origin_language", "en") or "en",
            collaborator_creator_tags=[
                str(t) for t in cls._row_json_list(row, "collaborator_creator_tags_json")
            ],
            primary_portrait_path=str(row["primary_portrait_path"]),
            avatar_path=cls._row_opt_str(row, "avatar_path"),
            card_image_path=cls._row_opt_str(row, "card_image_path"),
            appearance=cls._row_str(row, "appearance"),
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
                for x in cls._row_json_list(row, "dialogue_examples_json")
            ],
            linked_lorebook_ids=[int(x) for x in cls._row_json_list(row, "linked_lorebook_ids_json")],
            lorebook_world_conditions=world_conditions,
            suggested_worldinfo_id=cls._row_opt_int(row, "suggested_worldinfo_id"),
            first_message=str(row["first_message"]),
            initial_location_id=cls._row_opt_int(row, "initial_location_id"),
            initial_relationship=int(row["initial_relationship"]),
            preferred_location_ids=[int(x) for x in cls._row_json_list(row, "preferred_location_ids_json")],
            disliked_location_ids=[int(x) for x in cls._row_json_list(row, "disliked_location_ids_json")],
            gallery_images=gallery,
            sprites=sprites,
            created_at=parse_datetime(row["created_at"]),
        )
