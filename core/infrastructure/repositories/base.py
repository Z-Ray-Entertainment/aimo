from collections.abc import Callable
import sqlite3
from typing import Any, Generic, TypeVar

from infrastructure.database import get_db_session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository encapsulating standard SQLite data access and query patterns."""

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
