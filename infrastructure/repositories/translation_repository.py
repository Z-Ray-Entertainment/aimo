from datetime import datetime, timezone

from sqlalchemy import delete, select

from domain.translation.models import TranslationRecord
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import TranslationORM


class TranslationRepository:
    def get_translation(
        self,
        source_hash: str,
        target_lang: str,
    ) -> TranslationRecord | None:
        cleaned_lang = target_lang.strip().lower()[:2]
        with get_db_session() as session:
            stmt = select(TranslationORM).where(
                TranslationORM.source_hash == source_hash,
                TranslationORM.target_language == cleaned_lang,
            )
            orm_rec = session.execute(stmt).scalar_one_or_none()
            if orm_rec is None:
                return None
            return self._to_entity(orm_rec)

    def get_cache_dict(self, target_lang: str = "de") -> dict[str, str]:
        cleaned_lang = target_lang.strip().lower()[:2]
        with get_db_session() as session:
            stmt = select(TranslationORM).where(
                TranslationORM.target_language == cleaned_lang
            )
            rows = session.execute(stmt).scalars().all()
            cache: dict[str, str] = {}
            for row in rows:
                cache[row.source_hash] = row.translated_text
                cache[f"{row.source_hash}:{cleaned_lang}"] = row.translated_text
            return cache

    def save_translation(self, record: TranslationRecord) -> TranslationRecord:
        cleaned_lang = record.target_language.strip().lower()[:2]
        with get_db_session() as session:
            stmt = select(TranslationORM).where(
                TranslationORM.source_hash == record.source_hash,
                TranslationORM.target_language == cleaned_lang,
            )
            existing = session.execute(stmt).scalar_one_or_none()
            if existing is not None:
                existing.english_text = record.english_text
                existing.translated_text = record.translated_text
                existing.updated_at = datetime.now(timezone.utc)
                session.flush()
                return self._to_entity(existing)

            orm_rec = TranslationORM(
                source_hash=record.source_hash,
                english_text=record.english_text,
                target_language=cleaned_lang,
                translated_text=record.translated_text,
                updated_at=record.updated_at,
            )
            session.add(orm_rec)
            session.flush()
            return self._to_entity(orm_rec)

    def invalidate(self, source_hash: str) -> int:
        if not source_hash:
            return 0
        with get_db_session() as session:
            stmt = delete(TranslationORM).where(
                TranslationORM.source_hash == source_hash
            )
            res = session.execute(stmt)
            return int(res.rowcount or 0)

    @staticmethod
    def _to_entity(orm_rec: TranslationORM) -> TranslationRecord:
        return TranslationRecord(
            id=orm_rec.id,
            source_hash=orm_rec.source_hash,
            english_text=orm_rec.english_text,
            target_language=orm_rec.target_language,
            translated_text=orm_rec.translated_text,
            updated_at=orm_rec.updated_at,
        )
