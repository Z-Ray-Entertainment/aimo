from flask import Blueprint, render_template, request

from application.auth.decorators import get_current_user, require_auth
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository

overview_bp = Blueprint("overview", __name__)


@overview_bp.route("/")
@overview_bp.route("/overview")
@require_auth
def index():
    user = get_current_user()
    assert user is not None and user.id is not None

    char_repo = CharacterRepository()
    lb_repo = LorebookRepository()
    wi_repo = WorldInfoRepository()
    persona_repo = PersonaRepository()

    gender_filter = request.args.get("gender", "").strip().lower()
    chat_filter = request.args.get("chatted", "").strip().lower()
    sort_by = request.args.get("sort", "newest").strip().lower()
    active_tab = request.args.get("tab", "characters").strip().lower()
    if active_tab not in ("characters", "lorebooks", "worldinfo"):
        active_tab = "characters"

    raw_characters = char_repo.list_visible(user.id)
    character_cards = []
    for char in raw_characters:
        if char.id is None:
            continue
        if gender_filter and char.gender.value != gender_filter:
            continue
        msg_count = char_repo.get_message_count_for_user(char.id, user.id)
        if chat_filter == "chatted" and msg_count == 0:
            continue
        if chat_filter == "unchatted" and msg_count > 0:
            continue
        best_rel = char_repo.get_best_relationship_for_user(
            char.id, user.id, default_value=float(char.initial_relationship)
        )
        character_cards.append(
            {
                "character": char,
                "message_count": msg_count,
                "best_relationship": best_rel,
            }
        )

    if sort_by == "chatted_first":
        character_cards.sort(key=lambda c: c["message_count"], reverse=True)
    elif sort_by == "relationship":
        character_cards.sort(key=lambda c: c["best_relationship"], reverse=True)
    else:
        character_cards.sort(key=lambda c: c["character"].id or 0, reverse=True)

    lorebooks = lb_repo.list_visible(user.id)
    lorebook_cards = []
    for lb in lorebooks:
        if lb.id is None:
            continue
        entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=user.is_initial_admin)
        all_tags = []
        for e in entries:
            for t in e.tags:
                if t not in all_tags:
                    all_tags.append(t)
        lorebook_cards.append(
            {
                "lorebook": lb,
                "entry_count": len(entries),
                "tags": all_tags[:8],
            }
        )

    worldinfos = wi_repo.list_visible(user.id)
    worldinfo_cards = []
    for wi in worldinfos:
        if wi.id is None:
            continue
        locations = wi_repo.list_locations(wi.id)
        events = wi_repo.list_events(wi.id)
        worldinfo_cards.append(
            {
                "worldinfo": wi,
                "location_count": len(locations),
                "event_count": len(events),
            }
        )

    trans_repo = TranslationRepository()
    personas = persona_repo.list_for_user(user.id)
    persona_items = []
    for p in personas:
        p_trans = trans_repo.get_entity_translations_map("persona", p.id) if p.id else {}
        persona_items.append(
            {
                "persona": p,
                "in_use": persona_repo.is_used_in_any_session(p.id) if p.id else False,
                "i18n_description": p_trans.get("description", {}),
                "i18n_appearance": p_trans.get("appearance", {}),
            }
        )

    return render_template(
        "overview/index.html",
        character_cards=character_cards,
        lorebook_cards=lorebook_cards,
        lorebooks=lorebooks,
        worldinfo_cards=worldinfo_cards,
        persona_items=persona_items,
        gender_filter=gender_filter,
        chat_filter=chat_filter,
        sort_by=sort_by,
        active_tab=active_tab,
    )
