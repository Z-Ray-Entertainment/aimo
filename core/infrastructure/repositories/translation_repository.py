from datetime import datetime, timezone
import json
import sqlite3

from domain.translation.models import TranslationRecord, compute_source_hash
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

    def get_field_translations(
        self,
        entity_type: str,
        entity_id: int,
        field_name: str,
    ) -> dict[str, dict]:
        if not entity_id:
            return {}
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT language, text_content, is_outdated
                FROM entity_field_translations
                WHERE entity_type = ? AND entity_id = ? AND field_name = ?
                ORDER BY id ASC
                """,
                (entity_type, entity_id, field_name),
            ).fetchall()
            result: dict[str, dict] = {}
            for row in rows:
                lang = str(row["language"]).strip().lower()[:2]
                txt = str(row["text_content"])
                outdated = bool(row["is_outdated"])
                result[lang] = {
                    "text": txt,
                    "content": txt,
                    "outdated": outdated,
                    "is_outdated": outdated,
                }
            return result

    def get_entity_translations_map(
        self,
        entity_type: str,
        entity_id: int | None,
    ) -> dict[str, dict[str, dict]]:
        if not entity_id:
            return {}
        with get_db_session() as conn:
            rows = conn.execute(
                """
                SELECT field_name, language, text_content, is_outdated
                FROM entity_field_translations
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY id ASC
                """,
                (entity_type, entity_id),
            ).fetchall()
            mapping: dict[str, dict[str, dict]] = {}
            for row in rows:
                fname = str(row["field_name"])
                lang = str(row["language"]).strip().lower()[:2]
                txt = str(row["text_content"])
                outdated = bool(row["is_outdated"])
                mapping.setdefault(fname, {})[lang] = {
                    "text": txt,
                    "content": txt,
                    "outdated": outdated,
                    "is_outdated": outdated,
                }
            return mapping

    def save_field_translation(
        self,
        entity_type: str,
        entity_id: int,
        field_name: str,
        language: str,
        text_content: str = "",
        is_outdated: bool = False,
        content: str | None = None,
    ) -> None:
        final_text = (content if content is not None else text_content).strip()
        if not entity_id or not final_text:
            return
        cleaned_lang = language.strip().lower()[:2]
        now_str = format_datetime(datetime.now(timezone.utc))
        with get_db_session() as conn:
            conn.execute(
                """
                INSERT INTO entity_field_translations (
                    entity_type, entity_id, field_name, language, text_content, is_outdated, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_id, field_name, language) DO UPDATE SET
                    text_content = excluded.text_content,
                    is_outdated = excluded.is_outdated,
                    updated_at = excluded.updated_at
                """,
                (
                    entity_type,
                    entity_id,
                    field_name,
                    cleaned_lang,
                    final_text,
                    1 if is_outdated else 0,
                    now_str,
                ),
            )

    def save_field_variants_json(
        self,
        entity_type: str,
        entity_id: int | None,
        field_name: str,
        raw_json: str | None,
    ) -> None:
        if not entity_id or not raw_json:
            return
        try:
            parsed = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(parsed, dict):
            return
        variants = parsed.get("variants") if isinstance(parsed.get("variants"), dict) else parsed
        for lang, info in variants.items():
            if not isinstance(info, dict):
                continue
            txt = str(info.get("content") or info.get("text") or "").strip()
            outdated = bool(info.get("is_outdated") if "is_outdated" in info else info.get("outdated", False))
            if txt:
                self.save_field_translation(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    field_name=field_name,
                    language=str(lang),
                    text_content=txt,
                    is_outdated=outdated,
                )

    def get_localized_field(
        self,
        entity_type: str,
        entity_id: int | None,
        field_name: str,
        target_lang: str,
        default_text: str,
    ) -> str:
        cleaned_lang = target_lang.strip().lower()[:2] if target_lang else "en"
        if entity_id:
            variants = self.get_field_translations(entity_type, entity_id, field_name)
            if cleaned_lang in variants and variants[cleaned_lang].get("text", "").strip():
                return str(variants[cleaned_lang]["text"]).strip()
        if default_text and default_text.strip():
            rec = self.get_translation(compute_source_hash(default_text), cleaned_lang)
            if rec is not None and rec.translated_text.strip():
                return rec.translated_text.strip()
        return default_text

    def get_missing_languages(
        self,
        entity_type: str,
        entity_id: int,
        field_name: str,
        target_languages: list[str],
    ) -> list[str]:
        if not entity_id:
            return []
        existing = self.get_field_translations(entity_type, entity_id, field_name)
        missing: list[str] = []
        for lang in target_languages:
            code = lang.strip().lower()[:2]
            if not code:
                continue
            entry = existing.get(code)
            if entry is None or not str(entry.get("text", "")).strip() or bool(entry.get("is_outdated")):
                missing.append(code)
        return missing

    def is_entity_ready_for_language(
        self,
        entity_type: str,
        entity_id: int | None,
        language: str,
        required_fields: list[tuple[str, str]],
        origin_language: str = "en",
    ) -> bool:
        if not entity_id:
            return False
        cleaned_lang = (language or "en").strip().lower()[:2]
        cleaned_origin = (origin_language or "en").strip().lower()[:2]
        if cleaned_lang == cleaned_origin:
            return True
        trans_map = self.get_entity_translations_map(entity_type, entity_id)
        for field_name, base_value in required_fields:
            if not isinstance(base_value, str) or not base_value.strip():
                continue
            field_langs = trans_map.get(field_name, {})
            entry = field_langs.get(cleaned_lang)
            if entry is None or not str(entry.get("text", "")).strip():
                return False
        return True

    def delete_field_translations(
        self,
        entity_type: str,
        entity_id: int,
        field_name: str | None = None,
    ) -> int:
        if not entity_id:
            return 0
        with get_db_session() as conn:
            if field_name:
                cur = conn.execute(
                    "DELETE FROM entity_field_translations WHERE entity_type = ? AND entity_id = ? AND field_name = ?",
                    (entity_type, entity_id, field_name),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM entity_field_translations WHERE entity_type = ? AND entity_id = ?",
                    (entity_type, entity_id),
                )
            return int(cur.rowcount or 0)

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
