from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, has_creator_permission, require_auth
from application.core_client import core_get, core_post, core_put
from application.settings.forms import AccountForm
from application.ui_helpers import tr
from application.view_models import LANGUAGE_METADATA, wrap_dto
from i18n import gettext_noop as _

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


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

    all_items: list[dict] = []
    if type_filter in ("all", "character"):
        for c in wrap_dto(data.get("characters", [])):
            if not c.editable:
                continue
            if q and q not in (c.name or "").lower():
                continue
            all_items.append({"type": "character", "id": c.id, "name": c.name, "visibility": c.visibility, "url": url_for("characters.detail", character_id=c.id)})
    if type_filter in ("all", "worldinfo"):
        for w in wrap_dto(data.get("worldinfos", [])):
            if not w.editable:
                continue
            if q and q not in (w.name or "").lower():
                continue
            all_items.append({"type": "worldinfo", "id": w.id, "name": w.name, "visibility": w.visibility, "url": url_for("worldinfo.detail", worldinfo_id=w.id)})
    if type_filter in ("all", "lorebook"):
        for lb in wrap_dto(data.get("lorebooks", [])):
            if not lb.editable:
                continue
            if q and q not in (lb.name or "").lower():
                continue
            all_items.append({"type": "lorebook", "id": lb.id, "name": lb.name, "visibility": lb.visibility, "url": url_for("lorebooks.detail", lorebook_id=lb.id)})

    if sort_by == "name":
        all_items.sort(key=lambda item: (item["name"] or "").lower())
    else:
        all_items.sort(key=lambda item: item["id"] or 0, reverse=True)

    return render_template(
        "settings/creations.html",
        items=all_items,
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
