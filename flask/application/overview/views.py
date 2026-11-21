from flask import Blueprint, g, render_template, request

from application.auth.decorators import get_current_user, require_auth
from application.core_client import core_get
from application.view_models import wrap_dto

overview_bp = Blueprint("overview", __name__)


@overview_bp.route("/")
@overview_bp.route("/overview")
@require_auth
def index():
    user = get_current_user()
    gender_filter = request.args.get("gender", "all").strip().lower()
    chat_filter = request.args.get("chat", "all").strip().lower()
    author_filter = request.args.get("author", "all").strip().lower()
    visibility_filter = request.args.get("visibility", "all").strip().lower()
    sort_by = request.args.get("sort", "newest").strip().lower()
    active_tab = request.args.get("tab", "characters").strip().lower()
    if active_tab not in ("characters", "lorebooks", "worldinfos"):
        active_tab = "characters"

    status, data = core_get("/api/overview")
    if status != 200:
        data = {}

    sessions_all = wrap_dto(data.get("sessions", []))
    character_cards = []
    for char in wrap_dto(data.get("characters", [])):
        if gender_filter != "all" and str(getattr(char, "gender", "")).lower() != gender_filter:
            continue
        if visibility_filter != "all" and str(char.visibility).lower() != visibility_filter:
            continue
        if author_filter == "mine" and not char.editable:
            continue
        msg_count = int(getattr(char, "message_count", 0))
        if chat_filter == "chatted" and msg_count == 0:
            continue
        if chat_filter == "unchatted" and msg_count > 0:
            continue
        character_cards.append(
            {
                "character": char,
                "sessions": [s for s in sessions_all if s.character_id == char.id],
                "message_count": msg_count,
                "best_relationship": float(getattr(char, "best_relationship", 0.0)),
                "relationship_tier_name": getattr(char, "relationship_tier_name", "Stranger"),
                "is_editable": bool(char.editable),
                "translation_pending": bool(getattr(char, "translation_pending", False)),
            }
        )

    if sort_by == "name":
        character_cards.sort(key=lambda item: (item["character"].name or "").lower())
    elif sort_by == "chatted_first":
        character_cards.sort(key=lambda item: item["message_count"], reverse=True)
    elif sort_by == "relationship":
        character_cards.sort(key=lambda item: item["best_relationship"], reverse=True)
    else:
        character_cards.sort(key=lambda item: item["character"].id or 0, reverse=True)

    lorebook_cards = []
    lorebooks = wrap_dto(data.get("lorebooks", []))
    for lb in lorebooks:
        if visibility_filter != "all" and str(lb.visibility).lower() != visibility_filter:
            continue
        if author_filter == "mine" and not lb.editable:
            continue
        lorebook_cards.append(
            {
                "lorebook": lb,
                "entry_count": int(getattr(lb, "entry_count", 0)),
                "is_editable": bool(lb.editable),
                "translation_pending": bool(getattr(lb, "translation_pending", False)),
            }
        )

    worldinfo_cards = []
    for wi in wrap_dto(data.get("worldinfos", [])):
        if visibility_filter != "all" and str(wi.visibility).lower() != visibility_filter:
            continue
        if author_filter == "mine" and not wi.editable:
            continue
        worldinfo_cards.append(
            {
                "worldinfo": wi,
                "location_count": int(getattr(wi, "location_count", 0)),
                "event_count": int(getattr(wi, "event_count", 0)),
                "is_editable": bool(wi.editable),
                "translation_pending": bool(getattr(wi, "translation_pending", False)),
            }
        )

    persona_items = getattr(g, "persona_items", [])
    return render_template(
        "overview/index.html",
        character_cards=character_cards,
        lorebook_cards=lorebook_cards,
        lorebooks=lorebooks,
        worldinfo_cards=worldinfo_cards,
        persona_items=persona_items,
        gender_filter=gender_filter,
        chat_filter=chat_filter,
        author_filter=author_filter,
        visibility_filter=visibility_filter,
        sort_by=sort_by,
        active_tab=active_tab,
        has_missing_translations=bool(data.get("has_missing_translations", False)),
        current_user=user,
    )
