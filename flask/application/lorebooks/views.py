from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_auth, require_permission
from application.core_client import core_delete, core_get, core_post, core_put
from application.lorebooks.forms import LorebookEntryForm, LorebookForm
from application.ui_helpers import notify_author_translation_hint, tr
from application.view_models import FunctionPermission, wrap_dto
from i18n import gettext_noop as _

lorebooks_bp = Blueprint("lorebooks", __name__, url_prefix="/lorebooks")


@lorebooks_bp.route("/new", methods=["GET", "POST"])
@lorebooks_bp.route("/create", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def create():
    if request.method == "POST":
        form = LorebookForm.from_request(request.form)
        status, payload = core_post(
            "/api/lorebooks",
            json={
                "name": form.name,
                "description": form.description,
                "visibility": form.visibility,
                "is_proper_noun": form.is_proper_noun,
            },
        )
        if status < 400 and payload.get("id"):
            notify_author_translation_hint("lorebook", int(payload["id"]), "description")
            flash(tr(_("Lorebook '%(name)s' created."), name=payload.get("name", form.name)), "success")
            return redirect(url_for("lorebooks.detail", lorebook_id=payload["id"]))
        flash(payload.get("error") or tr(_("Failed to create lorebook.")), "error")
        return redirect(url_for("overview.index"))

    return render_template("lorebooks/new.html")


@lorebooks_bp.route("/<int:lorebook_id>", methods=["GET", "POST"])
@require_auth
def detail(lorebook_id: int):
    status, data = core_get(f"/api/lorebooks/{lorebook_id}")
    if status != 200:
        flash(tr(_("Lorebook not found.")), "error")
        return redirect(url_for("overview.index"))

    lorebook = wrap_dto(data)
    is_editable = bool(data.get("editable"))
    is_author = is_admin() or (get_current_user() and data.get("user_id") == get_current_user().id)

    if request.method == "POST":
        if not is_editable:
            flash(tr(_("Access denied: You can only edit your own lorebooks or creations shared with you.")), "error")
            return redirect(url_for("overview.index"))
        form = LorebookForm.from_request(request.form)
        upd_status, upd_data = core_put(
            f"/api/lorebooks/{lorebook_id}",
            json={
                "name": form.name,
                "description": form.description,
                "visibility": form.visibility,
                "is_proper_noun": form.is_proper_noun,
            },
        )
        if upd_status < 400:
            notify_author_translation_hint("lorebook", lorebook_id, "description")
            flash(tr(_("Lorebook updated.")), "success")
            return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))
        flash(upd_data.get("error") or tr(_("Failed to update lorebook.")), "error")

    return render_template(
        "lorebooks/detail.html",
        lorebook=lorebook,
        entries=wrap_dto(data.get("entries", [])),
        is_editable=is_editable,
        is_author=is_author,
        i18n_description=data.get("i18n_description", {}),
        entry_i18n={},
    )


@lorebooks_bp.route("/<int:lorebook_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def duplicate(lorebook_id: int):
    status, payload = core_post(f"/api/lorebooks/{lorebook_id}/duplicate")
    if status < 400 and payload.get("id"):
        flash(tr(_("Lorebook copied as '%(name)s'."), name=payload.get("name", "")), "success")
        return redirect(url_for("lorebooks.detail", lorebook_id=payload["id"]))
    flash(payload.get("error") or tr(_("Lorebook not found.")), "error")
    return redirect(url_for("overview.index"))


@lorebooks_bp.route("/<int:lorebook_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_DELETE)
def delete(lorebook_id: int):
    status, payload = core_delete(f"/api/lorebooks/{lorebook_id}")
    if status < 400:
        flash(tr(_("Lorebook deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Lorebook not found.")), "error")
    return redirect(url_for("overview.index"))


@lorebooks_bp.route("/<int:lorebook_id>/entries/add", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def add_entry(lorebook_id: int):
    form = LorebookEntryForm.from_request(request.form)
    status, payload = core_post(
        f"/api/lorebooks/{lorebook_id}/entries",
        json={
            "title": form.title,
            "tags": form.tags,
            "content": form.content,
            "visibility": form.visibility,
            "is_proper_noun": form.is_proper_noun,
        },
    )
    if status < 400:
        flash(tr(_("Entry '%(title)s' added."), title=form.title), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to add entry.")), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))


@lorebooks_bp.route("/<int:lorebook_id>/entries/<int:entry_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def edit_entry(lorebook_id: int, entry_id: int):
    form = LorebookEntryForm.from_request(request.form)
    status, payload = core_put(
        f"/api/lorebooks/entries/{entry_id}",
        json={
            "title": form.title,
            "tags": form.tags,
            "content": form.content,
            "visibility": form.visibility,
            "is_proper_noun": form.is_proper_noun,
        },
    )
    if status < 400:
        flash(tr(_("Entry updated.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to update entry.")), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))


@lorebooks_bp.route("/<int:lorebook_id>/entries/<int:entry_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def delete_entry(lorebook_id: int, entry_id: int):
    status, payload = core_delete(f"/api/lorebooks/entries/{entry_id}")
    if status < 400:
        flash(tr(_("Entry deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete entry.")), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))
