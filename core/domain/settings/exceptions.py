from shared.exceptions import DomainError


class SettingsError(DomainError):
    """Base exception for service settings and system prompt domain errors."""


class InvalidServiceUrlError(SettingsError):
    """Raised when a configured service URL is empty or malformed."""


class InvalidTaskModelError(SettingsError):
    """Raised when a task model assignment is invalid."""


class InvalidModelParametersError(SettingsError):
    """Raised when LLM inference parameters fall outside valid bounds."""


class InvalidSystemPromptError(SettingsError):
    """Raised when a required system prompt is empty."""
