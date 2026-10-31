import sqlite3

from domain.personas.models import Gender, UserPersona
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class PersonaRepository:
    def list_for_user(self, user_id: int) -> list[UserPersona]:
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM personas
                WHERE user_id = ?
                ORDER BY is_default DESC, id ASC
                """,
                (user_id,),
            ).fetchall()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, persona_id: int) -> UserPersona | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM personas WHERE id = ?",
                (persona_id,),
            ).fetchone()
            if row is None:
                return None
            return self._to_entity(row)

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
                    user_id, name, gender, portrait_path, description, appearance, is_default, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    persona.user_id,
                    persona.name,
                    persona.gender.value,
                    persona.portrait_path,
                    persona.description,
                    persona.appearance,
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
                SET name = ?, gender = ?, portrait_path = ?, description = ?, appearance = ?, is_default = ?
                WHERE id = ?
                """,
                (
                    persona.name,
                    persona.gender.value,
                    persona.portrait_path,
                    persona.description,
                    persona.appearance,
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
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM personas WHERE id = ?",
                (persona_id,),
            ).fetchone()
            if existing is None:
                return False
            conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
            return True

    def is_used_in_any_session(self, persona_id: int) -> bool:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chat_sessions WHERE persona_id = ?",
                (persona_id,),
            ).fetchone()
            return int(row["cnt"] if row is not None else 0) > 0

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
            is_default=bool(row["is_default"]),
            created_at=parse_datetime(row["created_at"]),
        )
