from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Memory:
    id: int | None
    chat_session_id: int
    message_idx: int
    title: str
    tags: list[str]
    summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
