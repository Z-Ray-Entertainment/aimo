from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_auth, require_permission
from application.core_client import core_delete, core_get, core_post, core_put
from application.ui_helpers import notify_author_translation_hint, tr
from application.view_models import FunctionPermission, wrap_dto
from application.worldinfo.forms import WorldInfoForm
from i18n import gettext_noop as _

worldinfo_bp = Blueprint("worldinfo", __name__, url_prefix="/worldinfo")


@worldinfo_bp.route("/new", methods=["GET", "POST"])
@worldinfo_bp.route("/create", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_CREATE)
def create():
    if request.method == "POST":
        form = WorldInfoForm.from_request(request.form)
        status, payload = core_post(
            "/api/worldinfo",
            json={
                "name": form.name,
                "icon": form.icon,
                "visibility": form.visibility,
                "lorebook_id": form.lorebook_id,
                "is_proper_noun": form.is_proper_noun,
            },
        )
        if status < 400 and payload.get("id"):
            notify_author_translation_hint("worldinfo", int(payload["id"]), "name")
            flash(tr(_("WorldInfo '%(name)s' created."), name=payload.get("name", form.name)), "success")
            return redirect(url_for("worldinfo.detail", worldinfo_id=payload["id"]))
        flash(payload.get("error") or tr(_("Failed to create WorldInfo.")), "error")
        return redirect(url_for("overview.index"))

    _, lb_data = core_get("/api/lorebooks")
    return render_template("worldinfo/new.html", lorebooks=wrap_dto(lb_data.get("lorebooks", [])))


@worldinfo_bp.route("/<int:worldinfo_id>", methods=["GET", "POST"])
@require_auth
def detail(worldinfo_id: int):
    status, data = core_get(f"/api/worldinfo/{worldinfo_id}")
    if status != 200:
        flash(tr(_("WorldInfo not found.")), "error")
        return redirect(url_for("overview.index"))

    worldinfo = wrap_dto(data)
    is_editable = bool(data.get("editable"))
    is_author = is_admin() or (get_current_user() and data.get("user_id") == get_current_user().id)

    if request.method == "POST":
        if not is_editable:
            flash(tr(_("Access denied: You can only edit your own WorldInfos or creations shared with you.")), "error")
            return redirect(url_for("overview.index"))
        form = WorldInfoForm.from_request(request.form)
        upd_status, upd_data = core_put(
            f"/api/worldinfo/{worldinfo_id}",
            json={
                "name": form.name,
                "icon": form.icon,
                "visibility": form.visibility,
                "lorebook_id": form.lorebook_id,
                "is_proper_noun": form.is_proper_noun,
            },
        )
        if upd_status < 400:
            flash(tr(_("WorldInfo updated.")), "success")
            return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))
        flash(upd_data.get("error") or tr(_("Failed to update WorldInfo.")), "error")

    _, lb_data = core_get("/api/lorebooks")
    _, char_data = core_get("/api/characters")
    return render_template(
        "worldinfo/detail.html",
        worldinfo=worldinfo,
        locations=wrap_dto(data.get("locations", [])),
        events=wrap_dto(data.get("events", [])),
        lorebooks=wrap_dto(lb_data.get("lorebooks", [])),
        characters=wrap_dto(char_data.get("characters", [])),
        is_editable=is_editable,
        is_author=is_author,
        active_tab=request.args.get("tab", "general"),
        location_i18n={},
        event_i18n={},
    )


@worldinfo_bp.route("/<int:worldinfo_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_CREATE)
def duplicate(worldinfo_id: int):
    status, payload = core_post(f"/api/worldinfo/{worldinfo_id}/duplicate")
    if status < 400 and payload.get("id"):
        flash(tr(_("WorldInfo copied as '%(name)s'."), name=payload.get("name", "")), "success")
        return redirect(url_for("worldinfo.detail", worldinfo_id=payload["id"]))
    flash(payload.get("error") or tr(_("WorldInfo not found.")), "error")
    return redirect(url_for("overview.index"))


@worldinfo_bp.route("/<int:worldinfo_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_DELETE)
def delete(worldinfo_id: int):
    status, payload = core_delete(f"/api/worldinfo/{worldinfo_id}")
    if status < 400:
        flash(tr(_("WorldInfo deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("WorldInfo not found.")), "error")
    return redirect(url_for("overview.index"))


from application.worldinfo import sub_views as _sub_views  # noqa: E402, F401
