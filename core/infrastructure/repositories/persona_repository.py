import sqlite3

from domain.personas.models import Gender, UserPersona
from infrastructure.database import get_db_session
from infrastructure.repositories.base import BaseRepository
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class PersonaRepository(BaseRepository[UserPersona]):
    def list_for_user(self, user_id: int) -> list[UserPersona]:
        return self._fetch_all(
            "SELECT * FROM personas WHERE user_id = ? ORDER BY is_default DESC, id ASC",
            (user_id,),
            self._to_entity,
        )

    def list_all(self) -> list[UserPersona]:
        return self._fetch_all(
            "SELECT * FROM personas ORDER BY id ASC",
            (),
            self._to_entity,
        )

    def get_by_id(self, persona_id: int) -> UserPersona | None:
        return self._get_by_id("personas", persona_id, self._to_entity)

    def get_default_for_user(self, user_id: int) -> UserPersona | None:
        personas = self.list_for_user(user_id)
        if not personas:
            return None
        for p in personas:
            if p.is_default:
                return p
        return personas[0]

    def create(self, persona: UserPersona) -> UserPersona:
        created_str = format_datetime(persona.created_at)
        with get_db_session() as conn:
            if persona.is_default:
                conn.execute(
                    "UPDATE personas SET is_default = 0 WHERE user_id = ?",
                    (persona.user_id,),
                )
            cursor = conn.execute(
                """
                INSERT INTO personas (
                    user_id, name, gender, portrait_path, description, appearance, origin_language, is_default, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    persona.user_id,
                    persona.name,
                    persona.gender.value,
                    persona.portrait_path,
                    persona.description,
                    persona.appearance,
                    getattr(persona, "origin_language", "en") or "en",
                    1 if persona.is_default else 0,
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM personas WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._to_entity(row)

    def update(self, persona: UserPersona) -> UserPersona:
        if persona.id is None:
            return self.create(persona)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM personas WHERE id = ?",
                (persona.id,),
            ).fetchone()
            if existing is None:
                return self.create(persona)
            if persona.is_default:
                conn.execute(
                    "UPDATE personas SET is_default = 0 WHERE user_id = ?",
                    (persona.user_id,),
                )
            conn.execute(
                """
                UPDATE personas
                SET name = ?, gender = ?, portrait_path = ?, description = ?, appearance = ?, origin_language = ?, is_default = ?
                WHERE id = ?
                """,
                (
                    persona.name,
                    persona.gender.value,
                    persona.portrait_path,
                    persona.description,
                    persona.appearance,
                    getattr(persona, "origin_language", "en") or "en",
                    1 if persona.is_default else 0,
                    persona.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM personas WHERE id = ?",
                (persona.id,),
            ).fetchone()
            return self._to_entity(row)

    def set_default(self, user_id: int, persona_id: int) -> None:
        with get_db_session() as conn:
            conn.execute(
                "UPDATE personas SET is_default = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.execute(
                "UPDATE personas SET is_default = 1 WHERE id = ? AND user_id = ?",
                (persona_id, user_id),
            )

    def delete(self, persona_id: int) -> bool:
        return self._delete_by_id("personas", persona_id)

    def is_used_in_any_session(self, persona_id: int) -> bool:
        return self._count("chat_sessions", "persona_id = ?", (persona_id,)) > 0

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> UserPersona:
        return UserPersona(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            gender=Gender.resolve(str(row["gender"])),
            portrait_path=str(row["portrait_path"]),
            description=str(row["description"]),
            appearance=str(row["appearance"]),
            origin_language=(
                str(row["origin_language"])
                if ("origin_language" in row.keys() and row["origin_language"])
                else "en"
            ),
            is_default=bool(row["is_default"]),
            created_at=parse_datetime(row["created_at"]),
        )
