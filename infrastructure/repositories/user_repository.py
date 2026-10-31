from sqlalchemy import func, select

from domain.auth.models import User
from domain.permissions.models import (
    PRESET_PERMISSIONS,
    Preset,
    UserPermissions,
)
from infrastructure.database import get_db_session
from infrastructure.repositories.orm_models import PermissionORM, UserORM


class UserRepository:
    def get_by_id(self, user_id: int) -> User | None:
        with get_db_session() as session:
            orm_user = session.get(UserORM, user_id)
            if orm_user is None:
                return None
            return self._to_entity(orm_user)

    def get_by_email(self, email: str) -> User | None:
        cleaned = email.strip().lower()
        with get_db_session() as session:
            stmt = select(UserORM).where(UserORM.email == cleaned)
            orm_user = session.execute(stmt).scalar_one_or_none()
            if orm_user is None:
                return None
            return self._to_entity(orm_user)

    def list_all(self) -> list[User]:
        with get_db_session() as session:
            stmt = select(UserORM).order_by(UserORM.id.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_entity(row) for row in rows]

    def create(self, user: User) -> User:
        with get_db_session() as session:
            orm_user = UserORM(
                username=user.username,
                email=user.email,
                password_hash=user.password_hash,
                is_initial_admin=user.is_initial_admin,
                created_at=user.created_at,
            )
            session.add(orm_user)
            session.flush()
            user.id = orm_user.id
            if user.is_initial_admin:
                for perm in PRESET_PERMISSIONS[Preset.ADMIN]:
                    session.add(PermissionORM(user_id=orm_user.id, permission=perm))
            return self._to_entity(orm_user)

    def update(self, user: User) -> User:
        if user.id is None:
            return self.create(user)
        with get_db_session() as session:
            orm_user = session.get(UserORM, user.id)
            if orm_user is None:
                return self.create(user)
            orm_user.username = user.username
            orm_user.email = user.email
            orm_user.password_hash = user.password_hash
            session.flush()
            return self._to_entity(orm_user)

    def delete(self, user_id: int) -> bool:
        with get_db_session() as session:
            orm_user = session.get(UserORM, user_id)
            if orm_user is None or orm_user.is_initial_admin:
                return False
            session.delete(orm_user)
            return True

    def count_users(self) -> int:
        with get_db_session() as session:
            stmt = select(func.count()).select_from(UserORM)
            return int(session.execute(stmt).scalar_one() or 0)

    def get_permissions(self, user_id: int) -> UserPermissions:
        with get_db_session() as session:
            orm_user = session.get(UserORM, user_id)
            if orm_user is not None and orm_user.is_initial_admin:
                return UserPermissions(
                    user_id=user_id,
                    permissions=set(PRESET_PERMISSIONS[Preset.ADMIN]),
                )
            stmt = select(PermissionORM).where(PermissionORM.user_id == user_id)
            rows = session.execute(stmt).scalars().all()
            return UserPermissions(
                user_id=user_id,
                permissions={row.permission for row in rows},
            )

    def save_permissions(self, user_perms: UserPermissions) -> None:
        with get_db_session() as session:
            orm_user = session.get(UserORM, user_perms.user_id)
            effective_perms = set(user_perms.permissions)
            if orm_user is not None and orm_user.is_initial_admin:
                effective_perms = set(PRESET_PERMISSIONS[Preset.ADMIN])

            stmt = select(PermissionORM).where(PermissionORM.user_id == user_perms.user_id)
            existing = session.execute(stmt).scalars().all()
            for item in existing:
                session.delete(item)
            session.flush()

            for perm in sorted(effective_perms):
                session.add(PermissionORM(user_id=user_perms.user_id, permission=perm))

    @staticmethod
    def _to_entity(orm_user: UserORM) -> User:
        return User(
            id=orm_user.id,
            username=orm_user.username,
            email=orm_user.email,
            password_hash=orm_user.password_hash,
            is_initial_admin=orm_user.is_initial_admin,
            created_at=orm_user.created_at,
        )
