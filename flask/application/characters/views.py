from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_auth, require_permission
from application.characters.forms import CharacterForm
from application.core_client import core_delete, core_get, core_post, core_put
from application.ui_helpers import notify_author_translation_hint, tr
from application.view_models import Emotion, FunctionPermission, Gender, wrap_dto
from i18n import gettext_noop as _

characters_bp = Blueprint("characters", __name__, url_prefix="/characters")


@characters_bp.route("/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def create():
    if request.method == "POST":
        form = CharacterForm.from_request(request.form)
        files = {}
        for key in ("primary_portrait", "avatar_portrait", "card_portrait"):
            f = request.files.get(key)
            if f and f.filename:
                files[key] = (f.filename, f.stream, f.mimetype or "application/octet-stream")
        form_data = {
            "name": form.name,
            "gender": form.gender,
            "description": form.description,
            "appearance": form.appearance,
            "first_message": form.first_message,
            "visibility": form.visibility,
            "initial_relationship": str(form.initial_relationship),
            "suggested_worldinfo_id": str(form.suggested_worldinfo_id or ""),
            "initial_location_id": str(form.initial_location_id or ""),
        }
        status, payload = core_post("/api/characters", data=form_data, files=files or None)
        if status < 400 and payload.get("id"):
            notify_author_translation_hint("character", int(payload["id"]), "description")
            flash(tr(_("Character '%(name)s' created."), name=payload.get("name", form.name)), "success")
            return redirect(url_for("characters.detail", character_id=payload["id"]))
        flash(payload.get("error") or tr(_("Failed to create character.")), "error")
        return redirect(url_for("overview.index"))

    _, lb_data = core_get("/api/lorebooks")
    _, wi_data = core_get("/api/worldinfo")
    return render_template(
        "characters/new.html",
        genders=[g.value for g in Gender],
        emotions=[e.value for e in Emotion],
        lorebooks=wrap_dto(lb_data.get("lorebooks", [])),
        worldinfos=wrap_dto(wi_data.get("worldinfos", [])),
    )


@characters_bp.route("/<int:character_id>", methods=["GET"])
@characters_bp.route("/<int:character_id>/edit", methods=["GET", "POST"])
@require_auth
def detail(character_id: int):
    status, data = core_get(f"/api/characters/{character_id}")
    if status != 200:
        flash(tr(_("Character not found.")), "error")
        return redirect(url_for("overview.index"))

    char = wrap_dto(data)
    is_editable = bool(data.get("editable"))
    is_author = is_admin() or (get_current_user() and data.get("user_id") == get_current_user().id)

    if request.method == "POST":
        if not is_editable:
            flash(tr(_("Access denied.")), "error")
            return redirect(url_for("overview.index"))
        form = CharacterForm.from_request(request.form)
        upd_status, upd_data = core_put(
            f"/api/characters/{character_id}",
            json={
                "name": form.name,
                "gender": form.gender,
                "description": form.description,
                "appearance": form.appearance,
                "first_message": form.first_message,
                "visibility": form.visibility,
                "initial_relationship": form.initial_relationship,
            },
        )
        if upd_status < 400:
            notify_author_translation_hint("character", character_id, "description")
            flash(tr(_("Character updated.")), "success")
            return redirect(url_for("characters.detail", character_id=character_id))
        flash(upd_data.get("error") or tr(_("Failed to update character.")), "error")

    _, lb_data = core_get("/api/lorebooks")
    _, wi_data = core_get("/api/worldinfo")
    return render_template(
        "characters/edit.html",
        character=char,
        is_editable=is_editable,
        is_author=is_author,
        genders=[g.value for g in Gender],
        emotions=[e.value for e in Emotion],
        lorebooks=wrap_dto(lb_data.get("lorebooks", [])),
        worldinfos=wrap_dto(wi_data.get("worldinfos", [])),
        character_events=wrap_dto(data.get("events", [])),
        char_i18n={},
        event_i18n={},
    )


@characters_bp.route("/<int:character_id>/copy", methods=["POST"])
@characters_bp.route("/<int:character_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def duplicate(character_id: int):
    status, payload = core_post(f"/api/characters/{character_id}/duplicate")
    if status < 400 and payload.get("id"):
        flash(tr(_("Character copied as '%(name)s'."), name=payload.get("name", "")), "success")
        return redirect(url_for("characters.detail", character_id=payload["id"]))
    flash(payload.get("error") or tr(_("Character not found.")), "error")
    return redirect(url_for("overview.index"))


@characters_bp.route("/<int:character_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_DELETE)
def delete(character_id: int):
    status, payload = core_delete(f"/api/characters/{character_id}")
    if status < 400:
        flash(tr(_("Character deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Character not found.")), "error")
    return redirect(url_for("overview.index"))


from application.characters import sub_views as _sub_views  # noqa: E402, F401
