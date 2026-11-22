import json
import sqlite3

from domain.memories.models import Memory
from infrastructure.database import format_datetime, get_db_session, parse_datetime
from infrastructure.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[Memory]):
    def list_for_session(self, session_id: int) -> list[Memory]:
        return self._fetch_all(
            "SELECT * FROM memories WHERE chat_session_id = ? ORDER BY message_idx ASC, id ASC",
            (session_id,),
            self._to_entity,
        )

    def get_by_id(self, memory_id: int) -> Memory | None:
        return self._get_by_id("memories", memory_id, self._to_entity)

    def add_memory(self, memory: Memory) -> Memory:
        created_str = format_datetime(memory.created_at)
        updated_str = format_datetime(memory.updated_at)
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories (
                    chat_session_id, message_idx, title, tags_json, summary, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.chat_session_id,
                    memory.message_idx,
                    memory.title,
                    json.dumps(memory.tags),
                    memory.summary,
                    created_str,
                    updated_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._to_entity(row)

    def update_memory(self, memory: Memory) -> Memory:
        if memory.id is None:
            return self.add_memory(memory)
        updated_str = format_datetime(memory.updated_at)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT id FROM memories WHERE id = ?",
                (memory.id,),
            ).fetchone()
            if existing is None:
                return self.add_memory(memory)
            conn.execute(
                """
                UPDATE memories
                SET title = ?, tags_json = ?, summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    memory.title,
                    json.dumps(memory.tags),
                    memory.summary,
                    updated_str,
                    memory.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory.id,),
            ).fetchone()
            return self._to_entity(row)

    def delete_memory(self, memory_id: int) -> bool:
        return self._delete_by_id("memories", memory_id)

    def delete_after_idx(self, session_id: int, message_idx: int) -> int:
        with get_db_session() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE chat_session_id = ? AND message_idx > ?",
                (session_id, message_idx),
            )
            return int(cursor.rowcount or 0)

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> Memory:
        try:
            tags = json.loads(str(row["tags_json"]))
        except json.JSONDecodeError:
            tags = []
        return Memory(
            id=int(row["id"]),
            chat_session_id=int(row["chat_session_id"]),
            message_idx=int(row["message_idx"]),
            title=str(row["title"]),
            tags=list(tags) if isinstance(tags, list) else [],
            summary=str(row["summary"]),
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
        )
