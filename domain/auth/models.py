from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class User:
    id: int | None
    username: str
    email: str
    password_hash: str
    is_initial_admin: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
