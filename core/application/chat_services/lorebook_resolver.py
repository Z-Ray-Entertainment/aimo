from __future__ import annotations

from typing import Any

from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository


def _format_lorebook_item(
    lb: Any,
    user_id: int,
    source: str,
    lb_repo: LorebookRepository,
    *,
    is_admin: bool = False,
    is_active: bool = True,
    is_locked: bool = False,
    required_worldinfo_id: int | None = None,
    required_worldinfo_name: str | None = None,
) -> dict[str, Any]:
    entries = lb_repo.list_entries(lb.id, user_id=user_id, is_admin=is_admin) if lb.id else []
    all_tags = sorted({t for e in entries for t in e.tags})
    is_private_to_user = lb.user_id != user_id and not is_admin and lb.visibility == "private"
    return {
        "id": lb.id,
        "name": lb.name,
        "description": lb.description,
        "tags": all_tags,
        "entry_count": len(entries),
        "source": source,
        "is_active": is_active,
        "is_locked": is_locked,
        "required_worldinfo_id": required_worldinfo_id,
        "required_worldinfo_name": required_worldinfo_name,
        "is_private_to_user": is_private_to_user,
    }


def resolve_session_lorebooks(
    user_id: int,
    character: Any,
    worldinfo: Any = None,
    chat_session: Any = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    lb_repo = LorebookRepository()
    wi_repo = WorldInfoRepository()
    all_visible = lb_repo.list_visible(user_id)
    all_map = {lb.id: lb for lb in all_visible if lb.id is not None}

    char_lb_ids = set(character.linked_lorebook_ids) if character else set()
    wi_lb_id = worldinfo.lorebook_id if (worldinfo and worldinfo.lorebook_id) else None
    char_conditions = getattr(character, "lorebook_world_conditions", {}) or {}

    default_ids = set(char_lb_ids)
    if wi_lb_id:
        default_ids.add(wi_lb_id)

    disabled_ids = set(chat_session.disabled_lorebook_ids) if chat_session else set()
    custom_ids = list(chat_session.custom_lorebook_ids) if chat_session else []
    active_wi_id = worldinfo.id if worldinfo else (chat_session.active_worldinfo_id if chat_session else None)

    default_lorebooks = []
    for lb_id in sorted(default_ids):
        lb = all_map.get(lb_id) or lb_repo.get_by_id(lb_id)
        if lb is None:
            continue
        in_char = lb_id in char_lb_ids
        in_wi = lb_id == wi_lb_id
        if in_char and in_wi:
            source = "Character & World"
        elif in_char:
            source = "Character"
        else:
            source = "World"

        is_locked = False
        req_wi_id = None
        req_wi_name = None
        if in_char and lb_id in char_conditions:
            req_wi_id = char_conditions[lb_id]
            req_wi = wi_repo.get_by_id(req_wi_id)
            req_wi_name = req_wi.name if req_wi else f"World #{req_wi_id}"
            if active_wi_id != req_wi_id:
                is_locked = True

        is_active = False if is_locked else (lb.id not in disabled_ids)
        default_lorebooks.append(
            _format_lorebook_item(
                lb,
                user_id,
                source,
                lb_repo,
                is_admin=is_admin,
                is_active=is_active,
                is_locked=is_locked,
                required_worldinfo_id=req_wi_id,
                required_worldinfo_name=req_wi_name,
            )
        )
    default_lorebooks.sort(key=lambda x: (x["name"] or "").lower())

    custom_lorebooks = []
    for lb_id in custom_ids:
        if lb_id in default_ids:
            continue
        lb = all_map.get(lb_id) or lb_repo.get_by_id(lb_id)
        if lb is None:
            continue
        custom_lorebooks.append(
            _format_lorebook_item(
                lb,
                user_id,
                "Custom",
                lb_repo,
                is_admin=is_admin,
                is_active=(lb.id not in disabled_ids),
            )
        )
    custom_lorebooks.sort(key=lambda x: (x["name"] or "").lower())

    active_in_session_ids = default_ids.union(custom_ids)
    available_lorebooks = []
    for lb in sorted(all_visible, key=lambda x: (x.name or "").lower()):
        entries = lb_repo.list_entries(lb.id, user_id=user_id, is_admin=is_admin) if lb.id else []
        all_tags = sorted({t for e in entries for t in e.tags})
        available_lorebooks.append(
            {
                "id": lb.id,
                "name": lb.name,
                "description": lb.description,
                "tags": all_tags,
                "entry_count": len(entries),
                "is_added": lb.id in active_in_session_ids,
            }
        )

    active_count = len([x for x in default_lorebooks if x["is_active"]]) + len(
        [x for x in custom_lorebooks if x["is_active"]]
    )
    return {
        "default_lorebooks": default_lorebooks,
        "custom_lorebooks": custom_lorebooks,
        "available_lorebooks": available_lorebooks,
        "active_count": active_count,
    }


def build_worldinfo_lorebooks_map(
    user_id: int,
    worldinfos: list[Any],
    is_admin: bool = False,
) -> dict[str, dict[str, Any]]:
    lb_repo = LorebookRepository()
    all_map = {lb.id: lb for lb in lb_repo.list_visible(user_id) if lb.id is not None}
    result: dict[str, dict[str, Any]] = {}
    for wi in worldinfos:
        if wi.id and wi.lorebook_id:
            lb = all_map.get(wi.lorebook_id) or lb_repo.get_by_id(wi.lorebook_id)
            if lb is not None:
                entries = lb_repo.list_entries(lb.id, user_id=user_id, is_admin=is_admin) if lb.id else []
                result[str(wi.id)] = {
                    "id": lb.id,
                    "name": lb.name,
                    "description": lb.description,
                    "tags": sorted({t for e in entries for t in e.tags}),
                    "entry_count": len(entries),
                    "source": "World",
                }
    return result
