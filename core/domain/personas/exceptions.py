from shared.exceptions import DomainError


class PersonaError(DomainError):
    """Base exception for persona domain errors."""


class PersonaNotFoundError(PersonaError):
    """Raised when a requested persona does not exist."""


class InvalidPersonaDataError(PersonaError):
    """Raised when persona attributes violate domain constraints."""


class PersonaInUseError(PersonaError):
    """Raised when attempting to delete a persona referenced in active chat sessions."""
