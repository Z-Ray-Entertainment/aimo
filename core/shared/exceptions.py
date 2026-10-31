class AimoError(Exception):
    """Base exception for all application errors in aimo."""


class DomainError(AimoError):
    """Base exception for domain layer business rule violations."""


class InfrastructureError(AimoError):
    """Base exception for persistence, file storage, and external provider errors."""


class ApplicationError(AimoError):
    """Base exception for orchestration, view, and REST API errors."""
