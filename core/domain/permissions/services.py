from domain.auth.models import User
from domain.permissions.exceptions import PermissionDeniedError, SuperAdminProtectionError
from domain.permissions.models import (
    PRESET_PERMISSIONS,
    FunctionPermission,
    Preset,
    UserPermissions,
)


class PermissionService:
    def assign_preset(
        self,
        user: User,
        user_perms: UserPermissions,
        preset: str | Preset,
    ) -> None:
        resolved_preset = Preset.resolve(preset)
        if user.is_initial_admin and resolved_preset != Preset.ADMIN:
            raise SuperAdminProtectionError(
                "The initial administrator cannot be downgraded from the Admin preset."
            )
        user_perms.permissions = set(PRESET_PERMISSIONS[resolved_preset])

    def grant_permission(
        self,
        user: User,
        user_perms: UserPermissions,
        permission: str | FunctionPermission,
    ) -> None:
        resolved = FunctionPermission.resolve(permission)
        if user.is_initial_admin:
            user_perms.permissions = set(PRESET_PERMISSIONS[Preset.ADMIN])
            return
        user_perms.permissions.add(resolved.value)

    def revoke_permission(
        self,
        user: User,
        user_perms: UserPermissions,
        permission: str | FunctionPermission,
    ) -> None:
        if user.is_initial_admin:
            raise SuperAdminProtectionError(
                "Permissions cannot be revoked from the initial administrator."
            )
        resolved = FunctionPermission.resolve(permission)
        user_perms.permissions.discard(resolved.value)

    def has_permission(
        self,
        user_perms: UserPermissions,
        permission: str | FunctionPermission,
    ) -> bool:
        try:
            resolved = FunctionPermission.resolve(permission)
        except ValueError:
            return False
        return resolved.value in user_perms.permissions or resolved.name in user_perms.permissions

    def require_permission(
        self,
        user_perms: UserPermissions,
        permission: str | FunctionPermission,
    ) -> None:
        if not self.has_permission(user_perms, permission):
            raise PermissionDeniedError(
                f"Missing required functional permission: '{permission}'."
            )

    def is_admin(self, user: User, user_perms: UserPermissions) -> bool:
        return user.is_initial_admin or self.has_permission(
            user_perms, FunctionPermission.ADMIN_ACCESS
        )

    def assert_modifiable_user(self, user: User) -> None:
        if user.is_initial_admin:
            raise SuperAdminProtectionError(
                "The initial administrator cannot be deactivated or deleted."
            )
