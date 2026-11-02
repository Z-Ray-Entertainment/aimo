from flask import g, request, session

from domain.auth.models import User
from domain.permissions.models import FunctionPermission, UserPermissions
from domain.permissions.services import PermissionService
from infrastructure.repositories.user_repository import UserRepository


class AuthContext:
    """Consolidated authentication and permission context for request-bound operations."""

    @staticmethod
    def get_current_user() -> User | None:
        if hasattr(g, "current_user"):
            return g.current_user

        raw_uid = (
            request.headers.get("X-User-Id")
            or session.get("user_id")
            or request.args.get("user_id")
        )
        if not raw_uid or not str(raw_uid).isdigit():
            g.current_user = None
            return None

        repo = UserRepository()
        user = repo.get_by_id(int(raw_uid))
        g.current_user = user
        return user

    @staticmethod
    def get_current_permissions() -> UserPermissions:
        if hasattr(g, "current_permissions"):
            return g.current_permissions
        user = AuthContext.get_current_user()
        if user is None or user.id is None:
            perms = UserPermissions(user_id=0, permissions=set())
        else:
            repo = UserRepository()
            perms = repo.get_permissions(user.id)
        g.current_permissions = perms
        return perms

    @staticmethod
    def has_permission(permission: str | FunctionPermission) -> bool:
        user = AuthContext.get_current_user()
        if user is None:
            return False
        if user.is_initial_admin:
            return True
        perms = AuthContext.get_current_permissions()
        return PermissionService().has_permission(perms, permission)

    @staticmethod
    def has_creator_permission() -> bool:
        user = AuthContext.get_current_user()
        if user is None:
            return False
        if user.is_initial_admin:
            return True
        perms = AuthContext.get_current_permissions()
        creator_perms = {
            FunctionPermission.CHARACTER_CREATE.value,
            FunctionPermission.CHARACTER_EDIT.value,
            FunctionPermission.WORLDINFO_CREATE.value,
            FunctionPermission.WORLDINFO_EDIT.value,
            FunctionPermission.LOREBOOK_CREATE.value,
            FunctionPermission.LOREBOOK_EDIT.value,
            FunctionPermission.ADMIN_ACCESS.value,
        }
        return any(p in perms.permissions for p in creator_perms)
