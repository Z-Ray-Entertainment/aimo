from shared.exceptions import DomainError


class CharacterError(DomainError):
    """Base exception for character domain errors."""


class CharacterNotFoundError(CharacterError):
    """Raised when a character does not exist."""


class InvalidCharacterDataError(CharacterError):
    """Raised when character attributes or assets are invalid."""
