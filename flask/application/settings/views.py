from datetime import datetime

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, has_creator_permission, require_auth
from application.core_client import core_get, core_post, core_put
from application.settings.forms import AccountForm
from application.ui_helpers import tr
from application.view_models import LANGUAGE_METADATA, wrap_dto
from i18n import gettext_noop as _

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

_GENDER_LABELS = {
    "female": _("Female"),
    "male": _("Male"),
    "non-binary": _("Non-Binary"),
}


def _format_created_at(raw_dt: str | None) -> str:
    if not raw_dt:
        return "—"
    try:
        return datetime.fromisoformat(raw_dt).strftime("%Y-%m-%d")
    except ValueError:
        return raw_dt[:10]


def _append_creation_items(
    target: list[dict],
    entities: list,
    *,
    user_id: int,
    role_filter: str,
    q: str,
    item_type: str,
    type_label: str,
    type_icon: str,
    build_fields,
) -> None:
    for entity in entities:
        name = entity.name or ""
        if q and q not in name.lower():
            continue
        is_owner = getattr(entity, "user_id", None) == user_id
        if role_filter in ("owner", "author", "mine") and not is_owner:
            continue
        if role_filter in ("collaboration", "collaborator", "collaborations") and is_owner:
            continue

        created_at_raw = getattr(entity, "created_at", None)
        extra = build_fields(entity)
        target.append(
            {
                "type": item_type,
                "type_label": type_label,
                "type_icon": type_icon,
                "id": entity.id,
                "name": name,
                "visibility": entity.visibility,
                "is_owner": is_owner,
                "role": "owner" if is_owner else "collaboration",
                "created_at_raw": created_at_raw or "",
                "created_at_formatted": _format_created_at(created_at_raw),
                **extra,
            }
        )


@settings_bp.route("/", methods=["GET"])
@require_auth
def index():
    return render_template("settings/index.html", current_user=get_current_user())


@settings_bp.route("/creations", methods=["GET"])
@require_auth
def creations():
    if not has_creator_permission():
        abort(403)
    user = get_current_user()
    type_filter = request.args.get("type", "all").strip().lower()
    role_filter = (
        request.args.get("role", "").strip().lower()
        or request.args.get("author", "").strip().lower()
        or "all"
    )
    q = request.args.get("q", "").strip().lower()
    sort_by = request.args.get("sort", "name").strip().lower()

    status, data = core_get("/api/overview")
    if status != 200:
        data = {}

    editable_chars = [c for c in wrap_dto(data.get("characters", [])) if c.editable]
    editable_worlds = [w for w in wrap_dto(data.get("worldinfos", [])) if w.editable]
    editable_lbs = [lb for lb in wrap_dto(data.get("lorebooks", [])) if lb.editable]

    char_count = len(editable_chars)
    world_count = len(editable_worlds)
    lorebook_count = len(editable_lbs)
    total_count = char_count + world_count + lorebook_count

    all_items: list[dict] = []
    if type_filter in ("all", "character", "characters"):
        _append_creation_items(
            all_items,
            editable_chars,
            user_id=user.id,
            role_filter=role_filter,
            q=q,
            item_type="characters",
            type_label=tr(_("Character")),
            type_icon="🎭",
            build_fields=lambda c: {
                "icon": "🎭",
                "image_path": getattr(c, "avatar_path", None) or getattr(c, "primary_portrait_path", None),
                "details": (
                    tr(_GENDER_LABELS[str(getattr(c, "gender", "")).lower()])
                    if str(getattr(c, "gender", "")).lower() in _GENDER_LABELS
                    else ""
                ),
                "editor_url": url_for("characters.edit_character", character_id=c.id),
            },
        )
    if type_filter in ("all", "worldinfo", "worlds", "world"):
        _append_creation_items(
            all_items,
            editable_worlds,
            user_id=user.id,
            role_filter=role_filter,
            q=q,
            item_type="worldinfo",
            type_label=tr(_("World")),
            type_icon="🌐",
            build_fields=lambda w: {
                "icon": getattr(w, "icon", None) or "🌐",
                "image_path": getattr(w, "cover_image_path", None),
                "details": f"{getattr(w, 'location_count', 0)} {tr(_('Locations'))} · {getattr(w, 'event_count', 0)} {tr(_('Events'))}",
                "editor_url": url_for("worldinfo.detail", worldinfo_id=w.id),
            },
        )
    if type_filter in ("all", "lorebook", "lorebooks"):
        _append_creation_items(
            all_items,
            editable_lbs,
            user_id=user.id,
            role_filter=role_filter,
            q=q,
            item_type="lorebooks",
            type_label=tr(_("Lorebook")),
            type_icon="📜",
            build_fields=lambda lb: {
                "icon": "📜",
                "image_path": None,
                "details": f"{getattr(lb, 'entry_count', 0)} {tr(_('Entries'))}",
                "editor_url": url_for("lorebooks.detail", lorebook_id=lb.id),
            },
        )

    if sort_by == "name":
        all_items.sort(key=lambda item: (item["name"] or "").lower())
    else:
        all_items.sort(key=lambda item: (item.get("created_at_raw") or "", item["id"] or 0), reverse=True)

    return render_template(
        "settings/creations.html",
        items=wrap_dto(all_items),
        total_count=total_count,
        char_count=char_count,
        world_count=world_count,
        lorebook_count=lorebook_count,
        type_filter=type_filter,
        role_filter=role_filter,
        sort_by=sort_by,
        q=q,
        current_user=user,
    )


@settings_bp.route("/account", methods=["GET"])
@require_auth
def account():
    return render_template("settings/account.html", languages=LANGUAGE_METADATA)


@settings_bp.route("/account", methods=["POST"])
@require_auth
def update_account():
    form = AccountForm.from_request(request.form)
    if form.new_password and form.new_password != form.confirm_password:
        flash(tr(_("The new passwords do not match.")), "error")
        return redirect(url_for("settings.account"))

    payload: dict = {
        "username": form.username,
        "language": form.language,
        "ember_particles_enabled": form.ember_particles_enabled,
    }
    if form.new_password:
        payload["current_password"] = form.current_password
        payload["new_password"] = form.new_password

    status, resp = core_put("/api/settings/profile", json=payload)
    if status < 400:
        core_post("/api/admin/translations/notify", json={})
        new_lang = (resp.get("language") or form.language or "en")[:2].lower()
        flash(tr(_("Account settings saved."), language=new_lang), "success")
        response = make_response(redirect(url_for("settings.account")))
        response.set_cookie("aimo_sys_lang", new_lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
        return response

    flash(resp.get("error") or tr(_("Failed to save account settings.")), "error")
    return redirect(url_for("settings.account"))
