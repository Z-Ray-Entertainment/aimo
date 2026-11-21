from __future__ import annotations

from typing import Any


def _format_lorebook_item(
    lb: Any,
    user_id: int,
    source: str,
    *,
    is_admin: bool = False,
    is_active: bool = True,
    is_locked: bool = False,
    required_worldinfo_id: int | None = None,
    required_worldinfo_name: str | None = None,
) -> dict[str, Any]:
    lb_user_id = getattr(lb, "user_id", None)
    visibility = getattr(lb, "visibility", "private")
    is_private_to_user = lb_user_id != user_id and not is_admin and visibility == "private"
    return {
        "id": lb.id,
        "name": lb.name,
        "description": getattr(lb, "description", "") or "",
        "tags": sorted(getattr(lb, "tags", []) or []),
        "entry_count": int(getattr(lb, "entry_count", 0) or 0),
        "source": source,
        "is_active": is_active,
        "is_locked": is_locked,
        "required_worldinfo_id": required_worldinfo_id,
        "required_worldinfo_name": required_worldinfo_name,
        "is_private_to_user": is_private_to_user,
    }


def build_lorebook_view_data(
    user_id: int,
    all_lorebooks: list[Any],
    worldinfos: list[Any],
    character: Any,
    worldinfo: Any = None,
    chat_session: Any = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    all_map = {lb.id: lb for lb in all_lorebooks if getattr(lb, "id", None) is not None}
    wi_map = {w.id: w for w in worldinfos if getattr(w, "id", None) is not None}

    char_lb_ids = set(getattr(character, "linked_lorebook_ids", []) or []) if character else set()
    wi_lb_id = getattr(worldinfo, "lorebook_id", None) if worldinfo else None
    raw_conditions = (getattr(character, "lorebook_world_conditions", {}) or {}) if character else {}
    char_conditions = {int(k): int(v) for k, v in raw_conditions.items() if str(k).isdigit() and str(v).isdigit()}

    default_ids = set(char_lb_ids)
    if wi_lb_id:
        default_ids.add(wi_lb_id)

    disabled_ids = set(getattr(chat_session, "disabled_lorebook_ids", []) or []) if chat_session else set()
    custom_ids = list(getattr(chat_session, "custom_lorebook_ids", []) or []) if chat_session else []
    active_wi_id = getattr(worldinfo, "id", None) if worldinfo else (
        getattr(chat_session, "active_worldinfo_id", None) if chat_session else None
    )

    default_lorebooks = []
    for lb_id in sorted(default_ids):
        lb = all_map.get(lb_id)
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
            req_wi = wi_map.get(req_wi_id)
            req_wi_name = req_wi.name if req_wi else f"World #{req_wi_id}"
            if active_wi_id != req_wi_id:
                is_locked = True

        is_active = False if is_locked else (lb.id not in disabled_ids)
        default_lorebooks.append(
            _format_lorebook_item(
                lb,
                user_id,
                source,
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
        lb = all_map.get(lb_id)
        if lb is None:
            continue
        custom_lorebooks.append(
            _format_lorebook_item(
                lb,
                user_id,
                "Custom",
                is_admin=is_admin,
                is_active=(lb.id not in disabled_ids),
            )
        )
    custom_lorebooks.sort(key=lambda x: (x["name"] or "").lower())

    active_in_session_ids = default_ids.union(custom_ids)
    available_lorebooks = [
        {
            "id": lb.id,
            "name": lb.name,
            "description": getattr(lb, "description", "") or "",
            "tags": sorted(getattr(lb, "tags", []) or []),
            "entry_count": int(getattr(lb, "entry_count", 0) or 0),
            "is_added": lb.id in active_in_session_ids,
        }
        for lb in sorted(all_lorebooks, key=lambda x: (x.name or "").lower())
    ]

    active_count = len([x for x in default_lorebooks if x["is_active"]]) + len(
        [x for x in custom_lorebooks if x["is_active"]]
    )
    return {
        "default_lorebooks": default_lorebooks,
        "custom_lorebooks": custom_lorebooks,
        "available_lorebooks": available_lorebooks,
        "active_count": active_count,
    }
