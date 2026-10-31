from shared.exceptions import DomainError


class TranslationError(DomainError):
    """Base exception for translation domain errors."""


class TranslationNotFoundError(TranslationError):
    """Raised when a translation record is not found."""


class InvalidTranslationDataError(TranslationError):
    """Raised when translation data is invalid."""
