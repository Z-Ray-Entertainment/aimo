from datetime import datetime
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for

from application.auth.decorators import (
    get_current_user,
    has_creator_permission,
    is_admin,
    require_auth,
)
from application.settings.forms import AccountForm
from domain.auth.services import AuthService
from domain.characters.models import Gender
from domain.translation.models import LANGUAGE_METADATA
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from shared.exceptions import AimoError

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET"])
@require_auth
def index():
    user = get_current_user()
    return render_template("settings/index.html", current_user=user)


@settings_bp.route("/creations", methods=["GET"])
@require_auth
def creations():
    user = get_current_user()
    if not has_creator_permission():
        abort(403)
    assert user is not None and user.id is not None

    char_repo = CharacterRepository()
    lb_repo = LorebookRepository()
    wi_repo = WorldInfoRepository()

    type_filter = request.args.get("type", "all").strip().lower()
    role_filter = (
        request.args.get("role", "").strip().lower()
        or request.args.get("author", "").strip().lower()
        or "all"
    )
    q = request.args.get("q", "").strip().lower()
    sort_by = request.args.get("sort", "name").strip().lower()

    # Query all user creations & collaborations
    creator_tag = user.creator_tag if user.creator_tag else None
    characters = char_repo.list_for_user_creations(user.id, creator_tag)
    worldinfos = wi_repo.list_for_user_creations(user.id, creator_tag)
    lorebooks = lb_repo.list_for_user_creations(user.id, creator_tag)

    all_items: list[dict] = []

    from i18n import gettext_noop as _, t
    ui_lang = (user.language or "en")[:2].lower()

    gender_labels = {
        Gender.FEMALE: t(_("Female"), ui_lang),
        Gender.MALE: t(_("Male"), ui_lang),
        Gender.NON_BINARY: t(_("Non-Binary"), ui_lang),
    }

    for c in characters:
        if c.id is None:
            continue
        g_label = gender_labels.get(c.gender, c.gender.value if hasattr(c.gender, "value") else str(c.gender))
        all_items.append({
            "type": "character",
            "type_label": t(_("Character"), ui_lang),
            "type_icon": "👤",
            "id": c.id,
            "name": c.name,
            "visibility": c.visibility,
            "is_owner": c.user_id == user.id,
            "role_label": t(_("Owner"), ui_lang) if c.user_id == user.id else t(_("Collaborator"), ui_lang),
            "created_at": c.created_at,
            "created_at_formatted": c.created_at.strftime("%d.%m.%Y") if c.created_at else "",
            "image_path": c.avatar_path or c.primary_portrait_path or None,
            "icon": None,
            "details": g_label,
            "editor_url": url_for(
                "characters.edit_character",
                character_id=c.id,
                return_to=request.full_path,
            ),
        })

    for w in worldinfos:
        if w.id is None:
            continue
        loc_count = len(wi_repo.list_locations(w.id))
        evt_count = len(wi_repo.list_events(w.id))
        all_items.append({
            "type": "worldinfo",
            "type_label": t(_("World"), ui_lang),
            "type_icon": "🌐",
            "id": w.id,
            "name": w.name,
            "visibility": w.visibility,
            "is_owner": w.user_id == user.id,
            "role_label": t(_("Owner"), ui_lang) if w.user_id == user.id else t(_("Collaborator"), ui_lang),
            "created_at": w.created_at,
            "created_at_formatted": w.created_at.strftime("%d.%m.%Y") if w.created_at else "",
            "image_path": w.cover_image_path or None,
            "icon": w.icon or "🌐",
            "details": f"{loc_count} {t(_('Locations'), ui_lang)} · {evt_count} {t(_('Events'), ui_lang)}",
            "editor_url": url_for(
                "worldinfo.detail",
                worldinfo_id=w.id,
                return_to=request.full_path,
            ),
        })

    for lb in lorebooks:
        if lb.id is None:
            continue
        entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin())
        all_items.append({
            "type": "lorebook",
            "type_label": t(_("Lorebook"), ui_lang),
            "type_icon": "📜",
            "id": lb.id,
            "name": lb.name,
            "visibility": lb.visibility,
            "is_owner": lb.user_id == user.id,
            "role_label": t(_("Owner"), ui_lang) if lb.user_id == user.id else t(_("Collaborator"), ui_lang),
            "created_at": lb.created_at,
            "created_at_formatted": lb.created_at.strftime("%d.%m.%Y") if lb.created_at else "",
            "image_path": None,
            "icon": "📜",
            "details": f"{len(entries)} {t(_('Entries'), ui_lang)}",
            "editor_url": url_for(
                "lorebooks.detail",
                lorebook_id=lb.id,
                return_to=request.full_path,
            ),
        })

    # Counts for filter pills
    total_count = len(all_items)
    char_count = sum(1 for i in all_items if i["type"] == "character")
    world_count = sum(1 for i in all_items if i["type"] == "worldinfo")
    lorebook_count = sum(1 for i in all_items if i["type"] == "lorebook")

    filtered_items = list(all_items)

    # Filter by type
    if type_filter == "characters":
        filtered_items = [i for i in filtered_items if i["type"] == "character"]
    elif type_filter == "worldinfo":
        filtered_items = [i for i in filtered_items if i["type"] == "worldinfo"]
    elif type_filter == "lorebooks":
        filtered_items = [i for i in filtered_items if i["type"] == "lorebook"]

    # Filter by role / author
    if role_filter in ("owner", "mine"):
        filtered_items = [i for i in filtered_items if i["is_owner"]]
    elif role_filter in ("collaboration", "collaborations"):
        filtered_items = [i for i in filtered_items if not i["is_owner"]]

    # Search filter
    if q:
        filtered_items = [
            i for i in filtered_items
            if q in i["name"].lower() or q in i["details"].lower() or q in i["type_label"].lower()
        ]

    # Sorting: Default alphabetical by name (A-Z)
    if sort_by == "newest":
        filtered_items.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
    else:
        sort_by = "name"
        filtered_items.sort(key=lambda x: x["name"].lower())

    return render_template(
        "settings/creations.html",
        current_user=user,
        items=filtered_items,
        total_count=total_count,
        char_count=char_count,
        world_count=world_count,
        lorebook_count=lorebook_count,
        type_filter=type_filter,
        role_filter=role_filter,
        sort_by=sort_by,
        q=q,
    )


@settings_bp.route("/account", methods=["GET"])
@require_auth
def account():
    return render_template(
        "settings/account.html",
        languages=LANGUAGE_METADATA,
    )


@settings_bp.route("/account", methods=["POST"])
@require_auth
def update_account():
    user = get_current_user()
    form = AccountForm.from_request(request.form)
    auth_service = AuthService()
    user_repo = UserRepository()
    import requests as http_requests
    from application.core_client import build_core_headers, get_core_base_url
    from i18n import gettext_noop as _, t

    ui_lang = (user.language or "en")[:2].lower()
    try:
        email_changed = form.email != user.email
        password_changed = bool(form.new_password)
        if email_changed or password_changed:
            if not auth_service.authenticate_user(user, form.current_password):
                raise AimoError(t(_("The current password is incorrect."), ui_lang))
        if email_changed:
            existing = user_repo.get_by_email(form.email)
            if existing is not None and existing.id != user.id:
                raise AimoError(t(_("A user with this email address already exists."), ui_lang))
        if password_changed and form.new_password != form.confirm_password:
            raise AimoError(t(_("The new passwords do not match."), ui_lang))

        auth_service.update_name(user, form.username)
        auth_service.update_email(user, form.email)
        auth_service.assign_language(user, form.language)
        auth_service.set_ember_particles_enabled(user, form.ember_particles_enabled)
        if password_changed:
            auth_service.change_password(user, form.new_password)
        user_repo.update(user)
        try:
            http_requests.post(
                f"{get_core_base_url()}/api/admin/translations/notify",
                headers=build_core_headers(),
                timeout=2,
            )
        except Exception:
            pass
        new_lang = (user.language or "en")[:2].lower()
        flash(t(_("Account settings saved."), new_lang), "success")
    except AimoError as exc:
        flash(str(exc), "error")
        return redirect(url_for("settings.account"))

    response = make_response(redirect(url_for("settings.account")))
    response.set_cookie("aimo_sys_lang", user.language, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return response
