import json

from sqlalchemy import select

from domain.lorebooks.models import Lorebook, LorebookEntry
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import LorebookEntryORM, LorebookORM


class LorebookRepository:
    def list_for_user(self, user_id: int | None = None) -> list[Lorebook]:
        with get_db_session() as session:
            stmt = select(LorebookORM).order_by(LorebookORM.id.asc())
            if user_id is not None:
                stmt = select(LorebookORM).order_by(LorebookORM.id.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, lorebook_id: int) -> Lorebook | None:
        with get_db_session() as session:
            orm_lb = session.get(LorebookORM, lorebook_id)
            if orm_lb is None:
                return None
            return self._to_entity(orm_lb)

    def create(self, lorebook: Lorebook) -> Lorebook:
        with get_db_session() as session:
            orm_lb = LorebookORM(
                user_id=lorebook.user_id,
                name=lorebook.name,
                description=lorebook.description,
                created_at=lorebook.created_at,
            )
            session.add(orm_lb)
            session.flush()
            return self._to_entity(orm_lb)

    def update(self, lorebook: Lorebook) -> Lorebook:
        if lorebook.id is None:
            return self.create(lorebook)
        with get_db_session() as session:
            orm_lb = session.get(LorebookORM, lorebook.id)
            if orm_lb is None:
                return self.create(lorebook)
            orm_lb.name = lorebook.name
            orm_lb.description = lorebook.description
            session.flush()
            return self._to_entity(orm_lb)

    def delete(self, lorebook_id: int) -> bool:
        with get_db_session() as session:
            orm_lb = session.get(LorebookORM, lorebook_id)
            if orm_lb is None:
                return False
            session.delete(orm_lb)
            return True

    def add_entry(self, entry: LorebookEntry) -> LorebookEntry:
        with get_db_session() as session:
            orm_entry = LorebookEntryORM(
                lorebook_id=entry.lorebook_id,
                title=entry.title,
                tags_json=json.dumps(entry.tags),
                content=entry.content,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
            session.add(orm_entry)
            session.flush()
            return self._entry_to_entity(orm_entry)

    def update_entry(self, entry: LorebookEntry) -> LorebookEntry:
        if entry.id is None:
            return self.add_entry(entry)
        with get_db_session() as session:
            orm_entry = session.get(LorebookEntryORM, entry.id)
            if orm_entry is None:
                return self.add_entry(entry)
            orm_entry.title = entry.title
            orm_entry.tags_json = json.dumps(entry.tags)
            orm_entry.content = entry.content
            orm_entry.updated_at = entry.updated_at
            session.flush()
            return self._entry_to_entity(orm_entry)

    def get_entry(self, entry_id: int) -> LorebookEntry | None:
        with get_db_session() as session:
            orm_entry = session.get(LorebookEntryORM, entry_id)
            if orm_entry is None:
                return None
            return self._entry_to_entity(orm_entry)

    def list_entries(self, lorebook_id: int) -> list[LorebookEntry]:
        with get_db_session() as session:
            stmt = (
                select(LorebookEntryORM)
                .where(LorebookEntryORM.lorebook_id == lorebook_id)
                .order_by(LorebookEntryORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._entry_to_entity(row) for row in rows]

    def list_entries_for_lorebooks(self, lorebook_ids: list[int]) -> list[LorebookEntry]:
        if not lorebook_ids:
            return []
        with get_db_session() as session:
            stmt = (
                select(LorebookEntryORM)
                .where(LorebookEntryORM.lorebook_id.in_(lorebook_ids))
                .order_by(LorebookEntryORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._entry_to_entity(row) for row in rows]

    def delete_entry(self, entry_id: int) -> bool:
        with get_db_session() as session:
            orm_entry = session.get(LorebookEntryORM, entry_id)
            if orm_entry is None:
                return False
            session.delete(orm_entry)
            return True

    @staticmethod
    def _to_entity(orm_lb: LorebookORM) -> Lorebook:
        return Lorebook(
            id=orm_lb.id,
            user_id=orm_lb.user_id,
            name=orm_lb.name,
            description=orm_lb.description,
            created_at=orm_lb.created_at,
        )

    @staticmethod
    def _entry_to_entity(orm_entry: LorebookEntryORM) -> LorebookEntry:
        try:
            tags = json.loads(orm_entry.tags_json)
        except json.JSONDecodeError:
            tags = []
        return LorebookEntry(
            id=orm_entry.id,
            lorebook_id=orm_entry.lorebook_id,
            title=orm_entry.title,
            tags=list(tags) if isinstance(tags, list) else [],
            content=orm_entry.content,
            created_at=orm_entry.created_at,
            updated_at=orm_entry.updated_at,
        )
