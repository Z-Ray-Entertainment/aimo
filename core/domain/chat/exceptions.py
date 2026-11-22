from shared.exceptions import DomainError


class ChatError(DomainError):
    """Base exception for chat domain errors."""


class ChatSessionNotFoundError(ChatError):
    """Raised when a chat session does not exist."""


class MessageNotFoundError(ChatError):
    """Raised when a chat message does not exist."""


class PersonaLockedError(ChatError):
    """Raised when attempting to change the persona after the first user message."""


class InvalidChatDataError(ChatError):
    """Raised when chat session or message data is invalid."""
