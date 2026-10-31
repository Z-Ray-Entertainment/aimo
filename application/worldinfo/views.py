from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_auth, require_permission
from application.worldinfo.forms import EventForm, LocationForm
from domain.permissions.models import FunctionPermission
from domain.worldinfo.services import WorldInfoService
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

worldinfo_bp = Blueprint("worldinfo", __name__, url_prefix="/worldinfo")


@worldinfo_bp.route("/create", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_CREATE)
def create_worldinfo():
    user = get_current_user()
    assert user is not None and user.id is not None
    service = WorldInfoService()
    repo = WorldInfoRepository()
    try:
        wi = service.create_worldinfo(
            user_id=user.id,
            name=request.form.get("name", ""),
            icon=request.form.get("icon", "🌐"),
            visibility=request.form.get("visibility", "private"),
        )
        saved = repo.create(wi)
        flash(f"WorldInfo '{saved.name}' erstellt.", "success")
        return redirect(url_for("worldinfo.detail", worldinfo_id=saved.id))
    except AimoError as exc:
        flash(str(exc), "error")
        return redirect(url_for("overview.index"))


@worldinfo_bp.route("/<int:worldinfo_id>", methods=["GET", "POST"])
@require_auth
def detail(worldinfo_id: int):
    repo = WorldInfoRepository()
    service = WorldInfoService()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None:
        flash("WorldInfo nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    if request.method == "POST":
        try:
            service.update_worldinfo(
                worldinfo=worldinfo,
                name=request.form.get("name", worldinfo.name),
                icon=request.form.get("icon", worldinfo.icon),
                visibility=request.form.get("visibility", worldinfo.visibility),
            )
            worldinfo = repo.update(worldinfo)
            flash("WorldInfo gespeichert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    locations = repo.list_locations(worldinfo_id)
    events = repo.list_events(worldinfo_id)
    loc_map = {loc.id: loc for loc in locations if loc.id is not None}

    trans_repo = TranslationRepository()
    location_translations = {
        loc.id: (
            trans_repo.get_entity_translations_map("worldinfo_location", loc.id)
            or trans_repo.get_entity_translations_map("location", loc.id)
        )
        for loc in locations
        if loc.id is not None
    }
    event_translations = {
        ev.id: (
            trans_repo.get_entity_translations_map("worldinfo_event", ev.id)
            or trans_repo.get_entity_translations_map("event", ev.id)
        )
        for ev in events
        if ev.id is not None
    }

    return render_template(
        "worldinfo/detail.html",
        worldinfo=worldinfo,
        locations=locations,
        events=events,
        loc_map=loc_map,
        loc_translations=location_translations,
        ev_translations=event_translations,
        location_translations=location_translations,
        event_translations=event_translations,
    )


@worldinfo_bp.route("/<int:worldinfo_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_DELETE)
def delete_worldinfo(worldinfo_id: int):
    repo = WorldInfoRepository()
    repo.delete(worldinfo_id)
    flash("WorldInfo gelöscht.", "success")
    return redirect(url_for("overview.index"))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_location(worldinfo_id: int):
    form = LocationForm.from_request(request.form)
    service = WorldInfoService()
    repo = WorldInfoRepository()
    storage = FileStorage()

    try:
        bg_path = form.background_image_path or None
        bg_file = request.files.get("background_file")
        if bg_file and bg_file.filename:
            bg_path = storage.save_background(bg_file.stream, bg_file.filename)

        loc = service.add_location(
            worldinfo_id=worldinfo_id,
            name=form.name,
            tags=form.tags,
            description=form.description,
            bg_path=bg_path,
            vision_alt_text=form.vision_alt_text or None,
        )
        saved_loc = repo.add_location(loc)
        TranslationRepository().save_field_variants_json(
            "worldinfo_location", saved_loc.id, "description", request.form.get("i18n_description")
        )
        flash(f"Ort '{loc.name}' angelegt.", "success")
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/<int:location_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def edit_location(worldinfo_id: int, location_id: int):
    form = LocationForm.from_request(request.form)
    service = WorldInfoService()
    repo = WorldInfoRepository()
    storage = FileStorage()

    loc = repo.get_location(location_id)
    if loc is not None:
        try:
            bg_path = form.background_image_path or loc.background_image_path
            bg_file = request.files.get("background_file")
            if bg_file and bg_file.filename:
                bg_path = storage.save_background(bg_file.stream, bg_file.filename)

            service.update_location(
                location=loc,
                name=form.name,
                tags=form.tags,
                description=form.description,
                bg_path=bg_path,
                vision_alt_text=form.vision_alt_text or loc.vision_alt_text,
            )
            repo.update_location(loc)
            TranslationRepository().save_field_variants_json(
                "worldinfo_location", loc.id, "description", request.form.get("i18n_description")
            )
            flash("Ort aktualisiert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/<int:location_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def delete_location(worldinfo_id: int, location_id: int):
    repo = WorldInfoRepository()
    repo.delete_location(location_id)
    flash("Ort gelöscht.", "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))


@worldinfo_bp.route("/<int:worldinfo_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_event(worldinfo_id: int):
    form = EventForm.from_request(request.form)
    service = WorldInfoService()
    repo = WorldInfoRepository()
    try:
        ev = service.add_event(
            worldinfo_id=worldinfo_id,
            title=form.title,
            description=form.description,
            probability=form.probability,
            one_shot=form.one_shot,
            location_id=form.location_id,
        )
        saved_ev = repo.add_event(ev)
        TranslationRepository().save_field_variants_json(
            "worldinfo_event", saved_ev.id, "description", request.form.get("i18n_description")
        )
        flash(f"Event '{ev.title}' hinzugefügt.", "success")
    except AimoError as exc:
        flash(str(exc), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))


@worldinfo_bp.route("/<int:worldinfo_id>/events/<int:event_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def edit_event(worldinfo_id: int, event_id: int):
    form = EventForm.from_request(request.form)
    service = WorldInfoService()
    repo = WorldInfoRepository()
    ev = repo.get_event(event_id)
    if ev is not None:
        try:
            service.update_event(
                event=ev,
                title=form.title,
                description=form.description,
                probability=form.probability,
                one_shot=form.one_shot,
                location_id=form.location_id,
            )
            repo.update_event(ev)
            TranslationRepository().save_field_variants_json(
                "worldinfo_event", ev.id, "description", request.form.get("i18n_description")
            )
            flash("Event aktualisiert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))


@worldinfo_bp.route("/<int:worldinfo_id>/events/<int:event_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def delete_event(worldinfo_id: int, event_id: int):
    repo = WorldInfoRepository()
    repo.delete_event(event_id)
    flash("Event gelöscht.", "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))
