import json
import sqlite3

from domain.lorebooks.models import Lorebook, LorebookEntry
from infrastructure.database import get_db_session
from infrastructure.repositories.base import BaseRepository
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class LorebookRepository(BaseRepository[Lorebook]):
    def list_visible(self, user_id: int) -> list[Lorebook]:
        return self._list_visible("lorebooks", user_id, self._to_entity)

    def list_for_user_creations(
        self, user_id: int, creator_tag: str | None = None
    ) -> list[Lorebook]:
        with get_db_session() as conn:
            if creator_tag:
                pattern = f"%{creator_tag.strip().lower()}%"
                rows = conn.execute(
                    """
                    SELECT * FROM lorebooks
                    WHERE user_id = ? OR collaborator_creator_tags_json LIKE ?
                    ORDER BY id DESC
                    """,
                    (user_id, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM lorebooks
                    WHERE user_id = ?
                    ORDER BY id DESC
                    """,
                    (user_id,),
                ).fetchall()
            entities = [self._to_entity(row) for row in rows]
            if creator_tag:
                normalized_tag = creator_tag.strip().lower()
                return [
                    lb
                    for lb in entities
                    if lb.user_id == user_id
                    or (
                        lb.collaborator_creator_tags
                        and normalized_tag
                        in [t.lower() for t in lb.collaborator_creator_tags]
                    )
                ]
            return entities

    def list_for_user(self, user_id: int | None = None) -> list[Lorebook]:
        if user_id is not None:
            return self.list_visible(user_id)
        return self._list_all("lorebooks", self._to_entity)

    def get_by_id(self, lorebook_id: int) -> Lorebook | None:
        return self._get_by_id("lorebooks", lorebook_id, self._to_entity)

    def create(self, lorebook: Lorebook) -> Lorebook:
        created_str = format_datetime(lorebook.created_at)
        tags_json = json.dumps(getattr(lorebook, "collaborator_creator_tags", []) or [])
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO lorebooks (user_id, name, description, visibility, origin_language, collaborator_creator_tags_json, is_proper_noun, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lorebook.user_id,
                    lorebook.name,
                    lorebook.description,
                    lorebook.visibility,
                    getattr(lorebook, "origin_language", "en") or "en",
                    tags_json,
                    1 if getattr(lorebook, "is_proper_noun", False) else 0,
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
        tags_json = json.dumps(getattr(lorebook, "collaborator_creator_tags", []) or [])
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
                SET name = ?, description = ?, visibility = ?, origin_language = ?, collaborator_creator_tags_json = ?, is_proper_noun = ?
                WHERE id = ?
                """,
                (
                    lorebook.name,
                    lorebook.description,
                    lorebook.visibility,
                    getattr(lorebook, "origin_language", "en") or "en",
                    tags_json,
                    1 if getattr(lorebook, "is_proper_noun", False) else 0,
                    lorebook.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM lorebooks WHERE id = ?",
                (lorebook.id,),
            ).fetchone()
            return self._to_entity(row)

    def delete(self, lorebook_id: int) -> bool:
        return self._delete_by_id("lorebooks", lorebook_id)

    def duplicate(self, lorebook_id: int, target_user_id: int) -> Lorebook:
        orig = self.get_by_id(lorebook_id)
        if orig is None:
            raise ValueError(f"Lorebook {lorebook_id} not found.")

        copy_name = f"{orig.name} (Kopie)"
        clone = Lorebook(
            id=None,
            user_id=target_user_id,
            name=copy_name,
            description=orig.description,
            visibility="private",
            collaborator_creator_tags=[],
            is_proper_noun=orig.is_proper_noun,
        )
        saved = self.create(clone)
        assert saved.id is not None

        # Duplicate entries
        orig_entries = self.list_entries(lorebook_id)
        for entry in orig_entries:
            clone_entry = LorebookEntry(
                id=None,
                lorebook_id=saved.id,
                title=entry.title,
                tags=list(entry.tags),
                content=entry.content,
                visibility=entry.visibility,
                is_proper_noun=entry.is_proper_noun,
            )
            self.add_entry(clone_entry)

        reloaded = self.get_by_id(saved.id)
        assert reloaded is not None
        return reloaded

    def add_entry(self, entry: LorebookEntry) -> LorebookEntry:
        created_str = format_datetime(entry.created_at)
        updated_str = format_datetime(entry.updated_at)
        vis = getattr(entry, "visibility", "public") or "public"
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO lorebook_entries (lorebook_id, title, tags_json, content, visibility, is_proper_noun, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.lorebook_id,
                    entry.title,
                    json.dumps(entry.tags),
                    entry.content,
                    vis,
                    1 if getattr(entry, "is_proper_noun", False) else 0,
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
        vis = getattr(entry, "visibility", "public") or "public"
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
                SET title = ?, tags_json = ?, content = ?, visibility = ?, is_proper_noun = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    entry.title,
                    json.dumps(entry.tags),
                    entry.content,
                    vis,
                    1 if getattr(entry, "is_proper_noun", False) else 0,
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
        return self._get_by_id("lorebook_entries", entry_id, self._entry_to_entity)

    def list_entries(
        self,
        lorebook_id: int,
        user_id: int | None = None,
        is_admin: bool = False,
    ) -> list[LorebookEntry]:
        all_entries = self._fetch_all(
            "SELECT * FROM lorebook_entries WHERE lorebook_id = ? ORDER BY id ASC",
            (lorebook_id,),
            self._entry_to_entity,
        )
        if user_id is None:
            return all_entries
        lorebook = self.get_by_id(lorebook_id)
        if lorebook is None:
            return []
        owner_id = lorebook.user_id
        return [
            e for e in all_entries
            if e.is_visible_to_user(owner_id, user_id, is_admin)
        ]

    def list_entries_for_lorebooks(self, lorebook_ids: list[int]) -> list[LorebookEntry]:
        if not lorebook_ids:
            return []
        placeholders = ",".join("?" for _ in lorebook_ids)
        return self._fetch_all(
            f"SELECT * FROM lorebook_entries WHERE lorebook_id IN ({placeholders}) ORDER BY id ASC",
            tuple(lorebook_ids),
            self._entry_to_entity,
        )

    def delete_entry(self, entry_id: int) -> bool:
        return self._delete_by_id("lorebook_entries", entry_id)

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> Lorebook:
        keys = row.keys()
        vis = str(row["visibility"]) if "visibility" in keys and row["visibility"] else "private"
        collaborator_tags = []
        if "collaborator_creator_tags_json" in keys and row["collaborator_creator_tags_json"]:
            try:
                parsed_tags = json.loads(row["collaborator_creator_tags_json"])
                collaborator_tags = [str(t) for t in parsed_tags if isinstance(parsed_tags, list)]
            except (json.JSONDecodeError, TypeError):
                collaborator_tags = []

        return Lorebook(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            visibility=vis,
            origin_language=(
                str(row["origin_language"])
                if ("origin_language" in row.keys() and row["origin_language"])
                else "en"
            ),
            collaborator_creator_tags=collaborator_tags,
            is_proper_noun=bool(row["is_proper_noun"]) if "is_proper_noun" in keys and row["is_proper_noun"] is not None else False,
            created_at=parse_datetime(row["created_at"]),
        )

    @staticmethod
    def _entry_to_entity(row: sqlite3.Row) -> LorebookEntry:
        try:
            tags = json.loads(row["tags_json"])
        except json.JSONDecodeError:
            tags = []
        keys = row.keys()
        vis = str(row["visibility"]) if ("visibility" in keys and row["visibility"]) else "public"
        return LorebookEntry(
            id=int(row["id"]),
            lorebook_id=int(row["lorebook_id"]),
            title=str(row["title"]),
            tags=list(tags) if isinstance(tags, list) else [],
            content=str(row["content"]),
            visibility=vis,
            is_proper_noun=bool(row["is_proper_noun"]) if "is_proper_noun" in keys and row["is_proper_noun"] is not None else False,
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
        )
