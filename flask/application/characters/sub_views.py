from flask import flash, redirect, request, url_for

from application.auth.decorators import require_permission
from application.characters.views import characters_bp
from application.core_client import core_delete, core_post, core_put
from application.ui_helpers import tr
from application.view_models import FunctionPermission
from application.worldinfo.forms import EventForm
from i18n import gettext_noop as _


@characters_bp.route("/<int:character_id>/gallery/add", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_gallery_image(character_id: int):
    file_obj = request.files.get("gallery_image")
    if not file_obj or not file_obj.filename:
        flash(tr(_("Please select a gallery image.")), "error")
        return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))
    status, payload = core_post(
        f"/api/characters/{character_id}/gallery",
        data={"unlock_threshold": request.form.get("unlock_threshold", "0")},
        files={"gallery_image": (file_obj.filename, file_obj.stream, file_obj.mimetype or "application/octet-stream")},
    )
    if status < 400:
        flash(tr(_("9:16 gallery image added.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to add gallery image.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))


@characters_bp.route("/<int:character_id>/gallery/<int:image_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def edit_gallery_image(character_id: int, image_id: int):
    status, payload = core_put(
        f"/api/characters/{character_id}/gallery/{image_id}",
        json={"unlock_threshold": int(request.form.get("unlock_threshold", 0))},
    )
    if status < 400:
        flash(tr(_("Gallery image updated.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to update gallery image.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))


@characters_bp.route("/<int:character_id>/gallery/<int:image_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_gallery_image(character_id: int, image_id: int):
    status, payload = core_delete(f"/api/characters/{character_id}/gallery/{image_id}")
    if status < 400:
        flash(tr(_("Gallery image removed.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete gallery image.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))


@characters_bp.route("/<int:character_id>/sprites/upload", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    file_obj = request.files.get("sprite")
    if not file_obj or not file_obj.filename:
        flash(tr(_("Please select a sprite image.")), "error")
        return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))
    status, payload = core_post(
        f"/api/characters/{character_id}/sprites",
        data={"emotion": request.form.get("emotion", "neutral")},
        files={"sprite": (file_obj.filename, file_obj.stream, file_obj.mimetype or "application/octet-stream")},
    )
    if status < 400:
        flash(tr(_("Sprite uploaded.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to upload sprite.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))


@characters_bp.route("/<int:character_id>/sprites/<string:emotion>/<int:variant>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_sprite(character_id: int, emotion: str, variant: int):
    status, payload = core_delete(f"/api/characters/{character_id}/sprites/{emotion}/{variant}")
    if status < 400:
        flash(tr(_("Sprite deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete sprite.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))


@characters_bp.route("/<int:character_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_event(character_id: int):
    form = EventForm.from_request(request.form)
    status, payload = core_post(
        f"/api/characters/{character_id}/events",
        json={
            "title": form.title,
            "i18n_title": request.form.get("i18n_title", ""),
            "description": form.description,
            "i18n_description": request.form.get("i18n_description", ""),
            "probability": form.probability,
            "one_shot": form.one_shot,
            "location_id": form.location_id,
        },
    )
    if status < 400:
        flash(tr(_("Event '%(title)s' added."), title=form.title), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to add event.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))


@characters_bp.route("/<int:character_id>/events/<int:event_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def edit_event(character_id: int, event_id: int):
    form = EventForm.from_request(request.form)
    status, payload = core_put(
        f"/api/characters/{character_id}/events/{event_id}",
        json={
            "title": form.title,
            "i18n_title": request.form.get("i18n_title", ""),
            "description": form.description,
            "i18n_description": request.form.get("i18n_description", ""),
            "probability": form.probability,
            "one_shot": form.one_shot,
            "location_id": form.location_id,
        },
    )
    if status < 400:
        flash(tr(_("Event updated.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to update event.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))


@characters_bp.route("/<int:character_id>/events/<int:event_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_event(character_id: int, event_id: int):
    status, payload = core_delete(f"/api/characters/{character_id}/events/{event_id}")
    if status < 400:
        flash(tr(_("Event deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete event.")), "error")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))
