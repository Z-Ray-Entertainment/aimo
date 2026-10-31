from shared.exceptions import DomainError


class LorebookError(DomainError):
    """Base exception for lorebook domain errors."""


class LorebookNotFoundError(LorebookError):
    """Raised when a lorebook cannot be found."""


class EntryNotFoundError(LorebookError):
    """Raised when a lorebook entry cannot be found."""


class InvalidLorebookDataError(LorebookError):
    """Raised when lorebook or entry data is invalid."""
