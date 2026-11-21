import sqlite3
import uuid

from domain.auth.models import User
from domain.permissions.models import (
    PRESET_PERMISSIONS,
    Preset,
    UserPermissions,
)
from infrastructure.database import get_db_session
from infrastructure.repositories.base import BaseRepository
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class UserRepository(BaseRepository[User]):
    def get_by_id(self, user_id: int) -> User | None:
        return self._get_by_id("users", user_id, self._to_entity)

    def get_by_email(self, email: str) -> User | None:
        return self._fetch_one(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
            self._to_entity,
        )

    def list_all(self) -> list[User]:
        return self._list_all("users", self._to_entity)

    def create(self, user: User) -> User:
        created_str = format_datetime(user.created_at)
        creator_tag = (user.creator_tag or str(uuid.uuid4())).strip()
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, email, password_hash, creator_tag, language, is_initial_admin, ember_particles_enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.username,
                    user.email.strip().lower(),
                    user.password_hash,
                    creator_tag,
                    user.language,
                    1 if user.is_initial_admin else 0,
                    1 if user.ember_particles_enabled else 0,
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            user.id = new_id
            user.creator_tag = creator_tag
            if user.is_initial_admin:
                for perm in sorted(PRESET_PERMISSIONS[Preset.ADMIN]):
                    conn.execute(
                        "INSERT INTO user_permissions (user_id, permission) VALUES (?, ?)",
                        (new_id, perm),
                    )
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (new_id,),
            ).fetchone()
            return self._to_entity(row)

    def update(self, user: User) -> User:
        if user.id is None:
            return self.create(user)
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user.id,),
            ).fetchone()
            if existing is None:
                return self.create(user)
            existing_tag = str(existing["creator_tag"]) if "creator_tag" in existing.keys() and existing["creator_tag"] else str(uuid.uuid4())
            tag_to_save = user.creator_tag.strip() if user.creator_tag and user.creator_tag.strip() else existing_tag
            conn.execute(
                """
                UPDATE users
                SET username = ?, email = ?, password_hash = ?, creator_tag = ?, language = ?, ember_particles_enabled = ?
                WHERE id = ?
                """,
                (
                    user.username,
                    user.email.strip().lower(),
                    user.password_hash,
                    tag_to_save,
                    user.language,
                    1 if user.ember_particles_enabled else 0,
                    user.id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user.id,),
            ).fetchone()
            return self._to_entity(row)

    def delete(self, user_id: int) -> bool:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT is_initial_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None or bool(row["is_initial_admin"]):
                return False
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return True

    def count_users(self) -> int:
        return self._count("users")

    def get_permissions(self, user_id: int) -> UserPermissions:
        with get_db_session() as conn:
            user_row = conn.execute(
                "SELECT is_initial_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user_row is not None and bool(user_row["is_initial_admin"]):
                return UserPermissions(
                    user_id=user_id,
                    permissions=set(PRESET_PERMISSIONS[Preset.ADMIN]),
                )
            rows = conn.execute(
                "SELECT permission FROM user_permissions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return UserPermissions(
                user_id=user_id,
                permissions={str(row["permission"]) for row in rows},
            )

    def save_permissions(self, user_perms: UserPermissions) -> None:
        with get_db_session() as conn:
            user_row = conn.execute(
                "SELECT is_initial_admin FROM users WHERE id = ?",
                (user_perms.user_id,),
            ).fetchone()
            effective_perms = set(user_perms.permissions)
            if user_row is not None and bool(user_row["is_initial_admin"]):
                effective_perms = set(PRESET_PERMISSIONS[Preset.ADMIN])

            conn.execute(
                "DELETE FROM user_permissions WHERE user_id = ?",
                (user_perms.user_id,),
            )
            for perm in sorted(effective_perms):
                conn.execute(
                    "INSERT INTO user_permissions (user_id, permission) VALUES (?, ?)",
                    (user_perms.user_id, perm),
                )

    def list_distinct_languages(self) -> list[str]:
        with get_db_session() as conn:
            rows = conn.execute(
                "SELECT DISTINCT LOWER(SUBSTR(TRIM(language), 1, 2)) AS lang FROM users WHERE TRIM(language) != ''"
            ).fetchall()
            langs: list[str] = ["en"]
            for row in rows:
                code = str(row["lang"] or "").strip()
                if code and code not in langs:
                    langs.append(code)
            return langs

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> User:
        tag = (
            str(row["creator_tag"])
            if ("creator_tag" in row.keys() and row["creator_tag"])
            else ""
        )
        return User(
            id=int(row["id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            password_hash=str(row["password_hash"]),
            creator_tag=tag,
            language=str(row["language"]) if "language" in row.keys() and row["language"] else "",
            is_initial_admin=bool(row["is_initial_admin"]),
            ember_particles_enabled=(
                bool(row["ember_particles_enabled"])
                if "ember_particles_enabled" in row.keys()
                else True
            ),
            created_at=parse_datetime(row["created_at"]),
        )
