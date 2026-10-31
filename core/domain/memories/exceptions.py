from shared.exceptions import DomainError


class MemoryError(DomainError):
    """Base exception for memory domain errors."""


class MemoryNotFoundError(MemoryError):
    """Raised when a memory does not exist."""


class InvalidMemoryDataError(MemoryError):
    """Raised when memory attributes are invalid."""
