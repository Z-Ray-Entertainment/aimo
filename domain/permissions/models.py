from dataclasses import dataclass, field
from enum import StrEnum


class FunctionPermission(StrEnum):
    ADMIN_ACCESS = "admin_access"
    CHARACTER_CREATE = "character_create"
    CHARACTER_EDIT = "character_edit"
    CHARACTER_DELETE = "character_delete"
    LOREBOOK_CREATE = "lorebook_create"
    LOREBOOK_EDIT = "lorebook_edit"
    LOREBOOK_DELETE = "lorebook_delete"
    WORLDINFO_CREATE = "worldinfo_create"
    WORLDINFO_EDIT = "worldinfo_edit"
    WORLDINFO_DELETE = "worldinfo_delete"
    CHAT_ACCESS = "chat_access"
    PERSONA_MANAGE = "persona_manage"

    @classmethod
    def resolve(cls, raw: str | "FunctionPermission") -> "FunctionPermission":
        if isinstance(raw, cls):
            return raw
        normalized = raw.strip()
        for member in cls:
            if normalized.lower() == member.value or normalized.upper() == member.name:
                return member
        raise ValueError(f"Unknown functional permission: '{raw}'")


class Preset(StrEnum):
    ADMIN = "Admin"
    CREATOR = "Creator"
    USER = "User"

    @classmethod
    def resolve(cls, raw: str | "Preset") -> "Preset":
        if isinstance(raw, cls):
            return raw
        normalized = raw.strip()
        for member in cls:
            if normalized.lower() == member.value.lower() or normalized.upper() == member.name:
                return member
        raise ValueError(f"Unknown permission preset: '{raw}'")


PRESET_PERMISSIONS: dict[Preset, frozenset[str]] = {
    Preset.ADMIN: frozenset(perm.value for perm in FunctionPermission),
    Preset.CREATOR: frozenset(
        {
            FunctionPermission.CHARACTER_CREATE.value,
            FunctionPermission.CHARACTER_EDIT.value,
            FunctionPermission.CHARACTER_DELETE.value,
            FunctionPermission.LOREBOOK_CREATE.value,
            FunctionPermission.LOREBOOK_EDIT.value,
            FunctionPermission.LOREBOOK_DELETE.value,
            FunctionPermission.WORLDINFO_CREATE.value,
            FunctionPermission.WORLDINFO_EDIT.value,
            FunctionPermission.WORLDINFO_DELETE.value,
            FunctionPermission.PERSONA_MANAGE.value,
            FunctionPermission.CHAT_ACCESS.value,
        }
    ),
    Preset.USER: frozenset(
        {
            FunctionPermission.CHAT_ACCESS.value,
            FunctionPermission.PERSONA_MANAGE.value,
        }
    ),
}


@dataclass
class UserPermissions:
    user_id: int
    permissions: set[str] = field(default_factory=set)
