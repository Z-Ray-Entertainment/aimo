import json
import sqlite3

from domain.lorebooks.models import Lorebook, LorebookEntry
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class LorebookRepository:
    def list_for_user(self, user_id: int | None = None) -> list[Lorebook]:
        with get_db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM lorebooks ORDER BY id ASC",
            ).fetchall()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, lorebook_id: int) -> Lorebook | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM lorebooks WHERE id = ?",
                (lorebook_id,),
            ).fetchone()
            if row is None:
                return None
            return self._to_entity(row)

    def create(self, lorebook: Lorebook) -> Lorebook:
        created_str = format_datetime(lorebook.created_at)
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO lorebooks (user_id, name, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    lorebook.user_id,
                    lorebook.name,
                    lorebook.description,
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM lorebooks WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._to_entity(row)

    def update(self, lorebook: Lorebook) -> Lorebook:
        if lorebook.id is None:
            return self.create(lorebook)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM lorebooks WHERE id = ?",
                (lorebook.id,),
            ).fetchone()
            if existing is None:
                return self.create(lorebook)
            conn.execute(
                """
                UPDATE lorebooks
                SET name = ?, description = ?
                WHERE id = ?
                """,
                (lorebook.name, lorebook.description, lorebook.id),
            )
            row = conn.execute(
                "SELECT * FROM lorebooks WHERE id = ?",
                (lorebook.id,),
            ).fetchone()
            return self._to_entity(row)

    def delete(self, lorebook_id: int) -> bool:
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM lorebooks WHERE id = ?",
                (lorebook_id,),
            ).fetchone()
            if existing is None:
                return False
            conn.execute("DELETE FROM lorebooks WHERE id = ?", (lorebook_id,))
            return True

    def add_entry(self, entry: LorebookEntry) -> LorebookEntry:
        created_str = format_datetime(entry.created_at)
        updated_str = format_datetime(entry.updated_at)
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO lorebook_entries (lorebook_id, title, tags_json, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.lorebook_id,
                    entry.title,
                    json.dumps(entry.tags),
                    entry.content,
                    created_str,
                    updated_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM lorebook_entries WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._entry_to_entity(row)

    def update_entry(self, entry: LorebookEntry) -> LorebookEntry:
        if entry.id is None:
            return self.add_entry(entry)
        updated_str = format_datetime(entry.updated_at)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM lorebook_entries WHERE id = ?",
                (entry.id,),
            ).fetchone()
            if existing is None:
                return self.add_entry(entry)
            conn.execute(
                """
                UPDATE lorebook_entries
                SET title = ?, tags_json = ?, content = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    entry.title,
                    json.dumps(entry.tags),
                    entry.content,
                    updated_str,
                    entry.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM lorebook_entries WHERE id = ?",
                (entry.id,),
            ).fetchone()
            return self._entry_to_entity(row)

    def get_entry(self, entry_id: int) -> LorebookEntry | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM lorebook_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if row is None:
                return None
            return self._entry_to_entity(row)

    def list_entries(self, lorebook_id: int) -> list[LorebookEntry]:
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM lorebook_entries
                WHERE lorebook_id = ?
                ORDER BY id ASC
                """,
                (lorebook_id,),
            ).fetchall()
            return [self._entry_to_entity(row) for row in rows]

    def list_entries_for_lorebooks(self, lorebook_ids: list[int]) -> list[LorebookEntry]:
        if not lorebook_ids:
            return []
        placeholders = ",".join("?" for _ in lorebook_ids)
        with get_db_session() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM lorebook_entries
                WHERE lorebook_id IN ({placeholders})
                ORDER BY id ASC
                """,
                tuple(lorebook_ids),
            ).fetchall()
            return [self._entry_to_entity(row) for row in rows]

    def delete_entry(self, entry_id: int) -> bool:
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM lorebook_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if existing is None:
                return False
            conn.execute("DELETE FROM lorebook_entries WHERE id = ?", (entry_id,))
            return True

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> Lorebook:
        return Lorebook(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            created_at=parse_datetime(row["created_at"]),
        )

    @staticmethod
    def _entry_to_entity(row: sqlite3.Row) -> LorebookEntry:
        try:
            tags = json.loads(row["tags_json"])
        except json.JSONDecodeError:
            tags = []
        return LorebookEntry(
            id=int(row["id"]),
            lorebook_id=int(row["lorebook_id"]),
            title=str(row["title"]),
            tags=list(tags) if isinstance(tags, list) else [],
            content=str(row["content"]),
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
        )
