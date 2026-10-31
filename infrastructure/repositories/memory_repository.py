import json

from sqlalchemy import delete, select

from domain.memories.models import Memory
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import MemoryORM


class MemoryRepository:
    def list_for_session(self, session_id: int) -> list[Memory]:
        with get_db_session() as session:
            stmt = (
                select(MemoryORM)
                .where(MemoryORM.chat_session_id == session_id)
                .order_by(MemoryORM.message_idx.asc(), MemoryORM.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, memory_id: int) -> Memory | None:
        with get_db_session() as session:
            orm_mem = session.get(MemoryORM, memory_id)
            if orm_mem is None:
                return None
            return self._to_entity(orm_mem)

    def add_memory(self, memory: Memory) -> Memory:
        with get_db_session() as session:
            orm_mem = MemoryORM(
                chat_session_id=memory.chat_session_id,
                message_idx=memory.message_idx,
                title=memory.title,
                tags_json=json.dumps(memory.tags),
                summary=memory.summary,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
            )
            session.add(orm_mem)
            session.flush()
            return self._to_entity(orm_mem)

    def update_memory(self, memory: Memory) -> Memory:
        if memory.id is None:
            return self.add_memory(memory)
        with get_db_session() as session:
            orm_mem = session.get(MemoryORM, memory.id)
            if orm_mem is None:
                return self.add_memory(memory)
            orm_mem.title = memory.title
            orm_mem.tags_json = json.dumps(memory.tags)
            orm_mem.summary = memory.summary
            orm_mem.updated_at = memory.updated_at
            session.flush()
            return self._to_entity(orm_mem)

    def delete_memory(self, memory_id: int) -> bool:
        with get_db_session() as session:
            orm_mem = session.get(MemoryORM, memory_id)
            if orm_mem is None:
                return False
            session.delete(orm_mem)
            return True

    def delete_after_idx(self, session_id: int, message_idx: int) -> int:
        with get_db_session() as session:
            stmt = delete(MemoryORM).where(
                MemoryORM.chat_session_id == session_id,
                MemoryORM.message_idx > message_idx,
            )
            res = session.execute(stmt)
            return int(res.rowcount or 0)

    @staticmethod
    def _to_entity(orm_mem: MemoryORM) -> Memory:
        try:
            tags = json.loads(orm_mem.tags_json)
        except json.JSONDecodeError:
            tags = []
        return Memory(
            id=orm_mem.id,
            chat_session_id=orm_mem.chat_session_id,
            message_idx=orm_mem.message_idx,
            title=orm_mem.title,
            tags=list(tags) if isinstance(tags, list) else [],
            summary=orm_mem.summary,
            created_at=orm_mem.created_at,
            updated_at=orm_mem.updated_at,
        )
