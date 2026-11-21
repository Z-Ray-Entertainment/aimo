from collections.abc import Callable
import json
import sqlite3
from typing import Any, Generic, TypeVar

from domain.base import PublishableEntityMixin
from infrastructure.database import get_db_session

T = TypeVar("T")
C = TypeVar("C", bound=PublishableEntityMixin)


class BaseRepository(Generic[T]):
    """Base repository encapsulating standard SQLite data access and row decoding."""

    @staticmethod
    def _row_str(row: sqlite3.Row, col: str, default: str = "") -> str:
        if col in row.keys() and row[col] is not None:
            return str(row[col])
        return default

    @staticmethod
    def _row_opt_str(row: sqlite3.Row, col: str) -> str | None:
        if col in row.keys() and row[col]:
            return str(row[col])
        return None

    @staticmethod
    def _row_opt_int(row: sqlite3.Row, col: str) -> int | None:
        if col in row.keys() and row[col] is not None:
            return int(row[col])
        return None

    @staticmethod
    def _row_bool(row: sqlite3.Row, col: str, default: bool = False) -> bool:
        if col in row.keys() and row[col] is not None:
            return bool(row[col])
        return default

    @staticmethod
    def _row_json_list(row: sqlite3.Row, col: str) -> list[Any]:
        if col not in row.keys() or not row[col]:
            return []
        try:
            val = json.loads(str(row[col]))
            return list(val) if isinstance(val, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _row_json_dict(row: sqlite3.Row, col: str) -> dict[Any, Any]:
        if col not in row.keys() or not row[col]:
            return {}
        try:
            val = json.loads(str(row[col]))
            return dict(val) if isinstance(val, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        mapper: Callable[[sqlite3.Row], T] | None = None,
    ) -> T | None:
        with get_db_session() as conn:
            row = conn.execute(query, params).fetchone()
            if row is None:
                return None
            return mapper(row) if mapper is not None else row  # type: ignore[return-value]

    def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        mapper: Callable[[sqlite3.Row], T] | None = None,
    ) -> list[T]:
        with get_db_session() as conn:
            rows = conn.execute(query, params).fetchall()
            if mapper is not None:
                return [mapper(row) for row in rows]
            return list(rows)  # type: ignore[return-value]

    def _get_by_id(
        self,
        table: str,
        entity_id: int,
        mapper: Callable[[sqlite3.Row], T],
    ) -> T | None:
        return self._fetch_one(
            f"SELECT * FROM {table} WHERE id = ?",
            (entity_id,),
            mapper,
        )

    def _delete_by_id(self, table: str, entity_id: int) -> bool:
        with get_db_session() as conn:
            cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (entity_id,))
            return cursor.rowcount > 0

    def _list_all(
        self,
        table: str,
        mapper: Callable[[sqlite3.Row], T],
        order_by: str = "id ASC",
    ) -> list[T]:
        return self._fetch_all(
            f"SELECT * FROM {table} ORDER BY {order_by}",
            (),
            mapper,
        )

    def _list_visible(
        self,
        table: str,
        user_id: int,
        mapper: Callable[[sqlite3.Row], T],
        order_by: str = "id ASC",
    ) -> list[T]:
        return self._fetch_all(
            f"SELECT * FROM {table} WHERE visibility = 'public' OR user_id = ? ORDER BY {order_by}",
            (user_id,),
            mapper,
        )

    def _count(
        self,
        table: str,
        where: str = "",
        params: tuple[Any, ...] = (),
    ) -> int:
        query = f"SELECT COUNT(*) AS cnt FROM {table}"
        if where:
            query += f" WHERE {where}"
        with get_db_session() as conn:
            row = conn.execute(query, params).fetchone()
            return int(row["cnt"] if row is not None else 0)


class CollaborativeRepository(BaseRepository[C]):
    """Base repository for publishable entities with collaborator_creator_tags."""

    def _rows_to_entities(self, conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[C]:
        raise NotImplementedError

    def _list_creations(
        self,
        table: str,
        user_id: int,
        creator_tag: str | None = None,
    ) -> list[C]:
        with get_db_session() as conn:
            if creator_tag:
                pattern = f"%{creator_tag.strip().lower()}%"
                rows = conn.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE user_id = ? OR collaborator_creator_tags_json LIKE ?
                    ORDER BY id DESC
                    """,
                    (user_id, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE user_id = ?
                    ORDER BY id DESC
                    """,
                    (user_id,),
                ).fetchall()
            entities = self._rows_to_entities(conn, rows)
            if creator_tag:
                normalized_tag = creator_tag.strip().lower()
                return [
                    e
                    for e in entities
                    if e.user_id == user_id
                    or (
                        e.collaborator_creator_tags
                        and normalized_tag in [tag.lower() for tag in e.collaborator_creator_tags]
                    )
                ]
            return entities
