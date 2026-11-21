from dataclasses import dataclass, field
from datetime import datetime

from domain.base import utc_now


@dataclass
class User:
    id: int | None
    username: str
    email: str
    password_hash: str
    creator_tag: str = ""
    language: str = ""
    is_initial_admin: bool = False
    ember_particles_enabled: bool = True
    created_at: datetime = field(default_factory=utc_now)
