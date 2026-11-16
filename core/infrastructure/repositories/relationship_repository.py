from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from domain.chat.relationship import (
    CANONICAL_RELATIONSHIP_TIERS,
    ORDERED_TIER_LEVELS,
    RelationshipTier,
    get_relationship_tier,
)
from infrastructure.database import create_connection, get_db_session


class RelationshipRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def get_tier(self, level: int | float, language: str = "en") -> RelationshipTier:
        step = get_relationship_tier(level).level
        lang_code = language.strip().lower()[:2] if language else "en"

        if lang_code and lang_code != "en":
            with get_db_session(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT name, description, behavior_rules
                    FROM relationship_tier_translations
                    WHERE level = ? AND language = ?
                    """,
                    (step, lang_code),
                ).fetchone()
                if row and row["name"]:
                    canonical = CANONICAL_RELATIONSHIP_TIERS.get(step)
                    rules = row["behavior_rules"] or (canonical.behavior_rules if canonical else "")
                    return RelationshipTier(
                        level=step,
                        name=str(row["name"]),
                        description=str(row["description"]),
                        behavior_rules=str(rules),
                    )

        with get_db_session(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT name, description, behavior_rules
                FROM relationship_tiers
                WHERE level = ?
                """,
                (step,),
            ).fetchone()
            if row:
                return RelationshipTier(
                    level=step,
                    name=str(row["name"]),
                    description=str(row["description"]),
                    behavior_rules=str(row["behavior_rules"]),
                )

        return CANONICAL_RELATIONSHIP_TIERS.get(step, CANONICAL_RELATIONSHIP_TIERS[0])

    def get_translations_map(self, language: str = "en") -> dict[int, RelationshipTier]:
        lang_code = language.strip().lower()[:2] if language else "en"
        result: dict[int, RelationshipTier] = {}

        if lang_code and lang_code != "en":
            with get_db_session(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT level, name, description, behavior_rules
                    FROM relationship_tier_translations
                    WHERE language = ?
                    """,
                    (lang_code,),
                ).fetchall()
                for r in rows:
                    lvl = int(r["level"])
                    canonical = CANONICAL_RELATIONSHIP_TIERS.get(lvl)
                    rules = r["behavior_rules"] or (canonical.behavior_rules if canonical else "")
                    result[lvl] = RelationshipTier(
                        level=lvl,
                        name=str(r["name"]),
                        description=str(r["description"]),
                        behavior_rules=str(rules),
                    )
        return result

    def list_tiers(self, language: str = "en") -> list[RelationshipTier]:
        trans_map = self.get_translations_map(language)
        return [
            trans_map.get(lvl, CANONICAL_RELATIONSHIP_TIERS[lvl])
            for lvl in ORDERED_TIER_LEVELS
            if lvl in CANONICAL_RELATIONSHIP_TIERS
        ]

    def save_translation(
        self,
        level: int | float,
        language: str,
        name: str,
        description: str,
        behavior_rules: str | None = None,
    ) -> None:
        lang_code = language.strip().lower()[:2] if language else "en"
        step = get_relationship_tier(level).level
        now_str = datetime.now(timezone.utc).isoformat()
        with get_db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO relationship_tier_translations
                    (level, language, name, description, behavior_rules, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(level, language) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    behavior_rules = excluded.behavior_rules,
                    updated_at = excluded.updated_at
                """,
                (step, lang_code, name.strip(), description.strip(), (behavior_rules or "").strip(), now_str),
            )
