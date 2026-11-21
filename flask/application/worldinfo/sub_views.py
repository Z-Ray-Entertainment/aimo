from flask import flash, redirect, request, url_for

from application.auth.decorators import require_permission
from application.core_client import core_delete, core_post
from application.ui_helpers import tr
from application.view_models import FunctionPermission
from application.worldinfo.forms import EventForm, LocationForm
from application.worldinfo.views import worldinfo_bp
from i18n import gettext_noop as _


@worldinfo_bp.route("/<int:worldinfo_id>/locations/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_location(worldinfo_id: int):
    form = LocationForm.from_request(request.form)
    status, payload = core_post(
        f"/api/worldinfo/{worldinfo_id}/locations",
        json={
            "name": form.name,
            "tags": form.tags,
            "description": form.description,
            "background_image_path": request.form.get("preuploaded_bg_path") or None,
        },
    )
    if status < 400:
        flash(tr(_("Location '%(name)s' added."), name=form.name), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to add location.")), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="locations"))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/<int:location_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def delete_location(worldinfo_id: int, location_id: int):
    status, payload = core_delete(f"/api/worldinfo/{worldinfo_id}/locations/{location_id}")
    if status < 400:
        flash(tr(_("Location deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete location.")), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="locations"))


@worldinfo_bp.route("/<int:worldinfo_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_event(worldinfo_id: int):
    form = EventForm.from_request(request.form)
    status, payload = core_post(
        "/api/worldinfo/events",
        json={
            "worldinfo_id": worldinfo_id,
            "location_id": form.location_id,
            "title": form.title,
            "description": form.description,
            "probability": form.probability,
            "one_shot": form.one_shot,
        },
    )
    if status < 400:
        flash(tr(_("Event '%(title)s' added."), title=form.title), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to add event.")), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="events"))


@worldinfo_bp.route("/<int:worldinfo_id>/events/<int:event_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def delete_event(worldinfo_id: int, event_id: int):
    status, payload = core_delete(f"/api/worldinfo/{worldinfo_id}/events/{event_id}")
    if status < 400:
        flash(tr(_("Event deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete event.")), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="events"))
