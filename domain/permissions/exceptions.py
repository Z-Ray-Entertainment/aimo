from shared.exceptions import DomainError


class PermissionDeniedError(DomainError):
    """Raised when a user lacks the required functional permission for an action."""


class SuperAdminProtectionError(DomainError):
    """Raised when attempting to revoke permissions, deactivate, or delete the initial administrator."""
