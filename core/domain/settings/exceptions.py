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


class InvalidLLMBackendError(SettingsError):
    """Raised when an unsupported LLM backend identifier is provided."""


class InvalidServiceCredentialsError(SettingsError):
    """Raised when required cloud API credentials are missing or invalid."""


class InvalidImageGenBackendError(SettingsError):
    """Raised when an unsupported image generation backend is provided."""


class InvalidSearchBackendError(SettingsError):
    """Raised when an unsupported search backend is provided."""
