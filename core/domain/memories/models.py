from dataclasses import dataclass, field
from datetime import datetime

from domain.base import utc_now


@dataclass
class Memory:
    id: int | None
    chat_session_id: int
    message_idx: int
    title: str
    tags: list[str]
    summary: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
