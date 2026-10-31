from shared.exceptions import DomainError


class AuthError(DomainError):
    """Base exception for authentication and user management domain errors."""


class DuplicateEmailError(AuthError):
    """Raised when attempting to register or assign an email address that already exists."""


class InvalidCredentialsError(AuthError):
    """Raised when authentication fails due to invalid email or password."""
