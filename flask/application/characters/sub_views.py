from flask import flash, redirect, request, url_for

from application.auth.decorators import require_permission
from application.characters.views import characters_bp
from application.core_client import core_delete, core_post
from application.ui_helpers import tr
from application.view_models import FunctionPermission
from application.worldinfo.forms import EventForm
from i18n import gettext_noop as _


@characters_bp.route("/<int:character_id>/sprites/upload", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    file_obj = request.files.get("sprite")
    if not file_obj or not file_obj.filename:
        flash(tr(_("Please select a sprite image.")), "error")
        return redirect(url_for("characters.detail", character_id=character_id))
    status, payload = core_post(
        f"/api/characters/{character_id}/sprites",
        data={"emotion": request.form.get("emotion", "neutral")},
        files={"sprite": (file_obj.filename, file_obj.stream, file_obj.mimetype or "application/octet-stream")},
    )
    if status < 400:
        flash(tr(_("Sprite uploaded.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to upload sprite.")), "error")
    return redirect(url_for("characters.detail", character_id=character_id))


@characters_bp.route("/<int:character_id>/sprites/<string:emotion>/<int:variant>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_sprite(character_id: int, emotion: str, variant: int):
    status, payload = core_delete(f"/api/characters/{character_id}/sprites/{emotion}/{variant}")
    if status < 400:
        flash(tr(_("Sprite deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete sprite.")), "error")
    return redirect(url_for("characters.detail", character_id=character_id))


@characters_bp.route("/<int:character_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_event(character_id: int):
    form = EventForm.from_request(request.form)
    status, payload = core_post(
        f"/api/characters/{character_id}/events",
        json={
            "title": form.title,
            "description": form.description,
            "probability": form.probability,
            "one_shot": form.one_shot,
            "location_id": form.location_id,
        },
    )
    if status < 400:
        flash(tr(_("Event '%(title)s' added."), title=form.title), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to add event.")), "error")
    return redirect(url_for("characters.detail", character_id=character_id))


@characters_bp.route("/<int:character_id>/events/<int:event_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_event(character_id: int, event_id: int):
    status, payload = core_delete(f"/api/characters/{character_id}/events/{event_id}")
    if status < 400:
        flash(tr(_("Event deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete event.")), "error")
    return redirect(url_for("characters.detail", character_id=character_id))
