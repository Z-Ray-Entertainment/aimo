from datetime import datetime, timezone
import sqlite3

from domain.translation.models import TranslationRecord
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class TranslationRepository:
    def get_translation(
        self,
        source_hash: str,
        target_lang: str,
    ) -> TranslationRecord | None:
        cleaned_lang = target_lang.strip().lower()[:2]
        with get_db_session() as conn:
            row = conn.execute(
                """
                SELECT * FROM translations
                WHERE source_hash = ? AND target_language = ?
                ORDER BY id DESC LIMIT 1
                """,
                (source_hash, cleaned_lang),
            ).fetchone()
            if row is None:
                return None
            return self._to_entity(row)

    def get_cache_dict(self, target_lang: str = "de") -> dict[str, str]:
        cleaned_lang = target_lang.strip().lower()[:2]
        with get_db_session() as conn:
            rows = conn.execute(
                "SELECT source_hash, translated_text FROM translations WHERE target_language = ?",
                (cleaned_lang,),
            ).fetchall()
            cache: dict[str, str] = {}
            for row in rows:
                sh = str(row["source_hash"])
                tt = str(row["translated_text"])
                cache[sh] = tt
                cache[f"{sh}:{cleaned_lang}"] = tt
            return cache

    def save_translation(self, record: TranslationRecord) -> TranslationRecord:
        cleaned_lang = record.target_language.strip().lower()[:2]
        now_str = format_datetime(datetime.now(timezone.utc))
        with get_db_session() as conn:
            existing = conn.execute(
                """
                SELECT id FROM translations
                WHERE source_hash = ? AND target_language = ?
                ORDER BY id DESC LIMIT 1
                """,
                (record.source_hash, cleaned_lang),
            ).fetchone()
            if existing is not None:
                rec_id = int(existing["id"])
                conn.execute(
                    """
                    UPDATE translations
                    SET english_text = ?, translated_text = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        record.english_text,
                        record.translated_text,
                        now_str,
                        rec_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO translations (
                        source_hash, english_text, target_language, translated_text, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.source_hash,
                        record.english_text,
                        cleaned_lang,
                        record.translated_text,
                        format_datetime(record.updated_at),
                    ),
                )
                rec_id = int(cursor.lastrowid or 0)
            row = conn.execute(
                "SELECT * FROM translations WHERE id = ?",
                (rec_id,),
            ).fetchone()
            return self._to_entity(row)

    def invalidate(self, source_hash: str) -> int:
        if not source_hash:
            return 0
        with get_db_session() as conn:
            cursor = conn.execute(
                "DELETE FROM translations WHERE source_hash = ?",
                (source_hash,),
            )
            return int(cursor.rowcount or 0)

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> TranslationRecord:
        return TranslationRecord(
            id=int(row["id"]),
            source_hash=str(row["source_hash"]),
            english_text=str(row["english_text"]),
            target_language=str(row["target_language"]),
            translated_text=str(row["translated_text"]),
            updated_at=parse_datetime(row["updated_at"]),
        )
