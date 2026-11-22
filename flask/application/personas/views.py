from flask import Blueprint, flash, redirect, request, url_for

from application.auth.decorators import require_permission
from application.core_client import core_delete, core_post, core_put
from application.ui_helpers import get_safe_back_url, notify_author_translation_hint, tr
from application.view_models import FunctionPermission, Gender
from i18n import gettext_noop as _

personas_bp = Blueprint("personas", __name__, url_prefix="/personas")


@personas_bp.route("/create", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def create_persona():
    preuploaded = request.form.get("preuploaded_portrait_path", "").strip()
    if preuploaded and (not preuploaded.startswith("portraits/") or ".." in preuploaded or preuploaded.startswith("/")):
        flash(tr(_("Invalid preuploaded portrait path.")), "error")
        return redirect(get_safe_back_url(url_for("overview.index")))

    files = {}
    portrait_file = request.files.get("portrait")
    if portrait_file and portrait_file.filename:
        files["portrait"] = (portrait_file.filename, portrait_file.stream, portrait_file.mimetype or "application/octet-stream")

    form_data = {
        "name": request.form.get("name", ""),
        "gender": request.form.get("gender", Gender.NON_BINARY.value),
        "description": request.form.get("description", ""),
        "appearance": request.form.get("appearance", ""),
        "is_default": "true" if request.form.get("is_default") else "false",
        "preuploaded_portrait_path": preuploaded,
        "i18n_description": request.form.get("i18n_description", ""),
        "i18n_appearance": request.form.get("i18n_appearance", ""),
    }
    status, payload = core_post("/api/personas", data=form_data, files=files or None)
    if status < 400:
        if payload.get("id"):
            notify_author_translation_hint("persona", int(payload["id"]), "description")
        flash(tr(_("Persona '%(name)s' created successfully."), name=payload.get("name", form_data["name"])), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to create persona.")), "error")
    return redirect(get_safe_back_url(url_for("overview.index")))


@personas_bp.route("/<int:persona_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def edit_persona(persona_id: int):
    preuploaded = request.form.get("preuploaded_portrait_path", "").strip()
    if preuploaded and (not preuploaded.startswith("portraits/") or ".." in preuploaded or preuploaded.startswith("/")):
        flash(tr(_("Invalid preuploaded portrait path.")), "error")
        return redirect(get_safe_back_url(url_for("overview.index")))

    files = {}
    portrait_file = request.files.get("portrait")
    if portrait_file and portrait_file.filename:
        files["portrait"] = (portrait_file.filename, portrait_file.stream, portrait_file.mimetype or "application/octet-stream")

    form_data = {
        "name": request.form.get("name", ""),
        "gender": request.form.get("gender", ""),
        "description": request.form.get("description", ""),
        "appearance": request.form.get("appearance", ""),
        "is_default": "true" if request.form.get("is_default") else "false",
        "preuploaded_portrait_path": preuploaded,
        "i18n_description": request.form.get("i18n_description", ""),
        "i18n_appearance": request.form.get("i18n_appearance", ""),
    }
    if files:
        status, payload = core_post(f"/api/personas/{persona_id}", data=form_data, files=files)
    else:
        status, payload = core_put(f"/api/personas/{persona_id}", json=form_data)
    if status < 400:
        flash(tr(_("Persona '%(name)s' updated."), name=payload.get("name", form_data["name"])), "success")
    else:
        flash(payload.get("error") or tr(_("Persona not found.")), "error")
    return redirect(get_safe_back_url(url_for("overview.index")))


@personas_bp.route("/<int:persona_id>/default", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def set_default(persona_id: int):
    status, payload = core_post(f"/api/personas/{persona_id}/default")
    if status < 400:
        flash(tr(_("'%(name)s' is now your default persona."), name=payload.get("name", "")), "success")
    else:
        flash(payload.get("error") or tr(_("Persona not found.")), "error")
    return redirect(get_safe_back_url(url_for("overview.index")))


@personas_bp.route("/<int:persona_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def delete_persona(persona_id: int):
    status, payload = core_delete(f"/api/personas/{persona_id}")
    if status < 400:
        flash(tr(_("Persona deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Persona not found.")), "error")
    return redirect(get_safe_back_url(url_for("overview.index")))
