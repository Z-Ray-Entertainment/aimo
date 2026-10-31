from shared.exceptions import DomainError


class WorldInfoError(DomainError):
    """Base exception for worldinfo domain errors."""


class WorldInfoNotFoundError(WorldInfoError):
    """Raised when a WorldInfo entity does not exist."""


class LocationNotFoundError(WorldInfoError):
    """Raised when a Location entity does not exist."""


class EventNotFoundError(WorldInfoError):
    """Raised when an Event entity does not exist."""


class InvalidWorldInfoDataError(WorldInfoError):
    """Raised when WorldInfo, Location, or Event data is invalid."""
