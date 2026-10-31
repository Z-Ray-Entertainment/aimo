import sqlite3

from domain.auth.models import User
from domain.permissions.models import (
    PRESET_PERMISSIONS,
    Preset,
    UserPermissions,
)
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import format_datetime, parse_datetime


class UserRepository:
    def get_by_id(self, user_id: int) -> User | None:
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            return self._to_entity(row)

    def get_by_email(self, email: str) -> User | None:
        cleaned = email.strip().lower()
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (cleaned,),
            ).fetchone()
            if row is None:
                return None
            return self._to_entity(row)

    def list_all(self) -> list[User]:
        with get_db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY id ASC",
            ).fetchall()
            return [self._to_entity(row) for row in rows]

    def create(self, user: User) -> User:
        created_str = format_datetime(user.created_at)
        with get_db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, email, password_hash, is_initial_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user.username,
                    user.email.strip().lower(),
                    user.password_hash,
                    1 if user.is_initial_admin else 0,
                    created_str,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            user.id = new_id
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
            conn.execute(
                """
                UPDATE users
                SET username = ?, email = ?, password_hash = ?
                WHERE id = ?
                """,
                (
                    user.username,
                    user.email.strip().lower(),
                    user.password_hash,
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
        with get_db_session() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
            return int(row["cnt"] if row is not None else 0)

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

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> User:
        return User(
            id=int(row["id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            password_hash=str(row["password_hash"]),
            is_initial_admin=bool(row["is_initial_admin"]),
            created_at=parse_datetime(row["created_at"]),
        )
