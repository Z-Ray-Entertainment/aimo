from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_auth, require_permission
from application.worldinfo.forms import EventForm, LocationForm
from domain.permissions.models import FunctionPermission
from domain.worldinfo.services import WorldInfoService
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
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
        raw_lb = request.form.get("lorebook_id", "").strip()
        lb_id = int(raw_lb) if raw_lb and raw_lb.isdigit() and int(raw_lb) > 0 else None
        wi = service.create_worldinfo(
            user_id=user.id,
            name=request.form.get("name", ""),
            icon="🌐",
            visibility=request.form.get("visibility", "private"),
            lorebook_id=lb_id,
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
    user = get_current_user()
    assert user is not None and user.id is not None

    repo = WorldInfoRepository()
    service = WorldInfoService()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_visible_to_user(user.id, user.is_initial_admin):
        flash("WorldInfo nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    is_editable = worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag)
    is_author = (worldinfo.user_id == user.id or user.is_initial_admin)

    if request.method == "POST":
        if not is_editable:
            flash("Zugriff verweigert: Du kannst nur deine eigenen WorldInfos oder für dich freigegebene Kreationen bearbeiten.", "error")
            return redirect(url_for("overview.index"))
        try:
            storage = FileStorage()
            cover_path = worldinfo.cover_image_path
            cover_file = request.files.get("cover_file")
            if cover_file and cover_file.filename:
                cover_path = storage.save_cover(cover_file.stream, cover_file.filename)

            raw_lb = request.form.get("lorebook_id", "").strip()
            lb_id = int(raw_lb) if raw_lb and raw_lb.isdigit() and int(raw_lb) > 0 else None

            collaborator_tags = None
            if is_author and "collaborator_creator_tags" in request.form:
                raw_collab = request.form.get("collaborator_creator_tags", "")
                collaborator_tags = [t.strip().lower() for t in raw_collab.split(",") if t.strip()]

            service.update_worldinfo(
                worldinfo=worldinfo,
                name=request.form.get("name", worldinfo.name),
                icon=worldinfo.icon or "🌐",
                visibility=request.form.get("visibility", worldinfo.visibility),
                cover_image_path=cover_path,
                lorebook_id=lb_id,
                collaborator_creator_tags=collaborator_tags,
            )
            worldinfo = repo.update(worldinfo)
            flash("WorldInfo gespeichert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    locations = repo.list_locations(worldinfo_id)
    events = repo.list_events(worldinfo_id)
    loc_map = {loc.id: loc for loc in locations if loc.id is not None}

    lb_repo = LorebookRepository()
    lorebooks = lb_repo.list_visible(user.id)

    char_repo = CharacterRepository()
    available_characters = char_repo.list_visible(user.id)
    character_map = {c.id: c for c in available_characters if c.id is not None}
    for loc in locations:
        if loc.character_id and loc.character_id not in character_map:
            c = char_repo.get_by_id(loc.character_id)
            if c and c.id is not None:
                character_map[c.id] = c

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

    valid_tabs = ("info", "places", "events", "collab")
    active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
    if active_tab not in valid_tabs:
        active_tab = "info"

    return render_template(
        "worldinfo/detail.html",
        worldinfo=worldinfo,
        is_editable=is_editable,
        is_author=is_author,
        active_tab=active_tab,
        lorebooks=lorebooks,
        locations=locations,
        events=events,
        available_characters=available_characters,
        character_map=character_map,
        loc_map=loc_map,
        loc_translations=location_translations,
        ev_translations=event_translations,
        location_translations=location_translations,
        event_translations=event_translations,
    )


@worldinfo_bp.route("/<int:worldinfo_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_CREATE)
def duplicate_worldinfo(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    orig = repo.get_by_id(worldinfo_id)
    if orig is None or not orig.is_visible_to_user(user.id, user.is_initial_admin):
        flash("WorldInfo nicht gefunden.", "error")
        return redirect(url_for("overview.index", tab="worldinfo"))
    copied = repo.duplicate(worldinfo_id, user.id)
    flash(f"Kopie '{copied.name}' erfolgreich angelegt.", "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=copied.id))


@worldinfo_bp.route("/<int:worldinfo_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_DELETE)
def delete_worldinfo(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_deletable_by_user(user.id, user.is_initial_admin):
        flash("WorldInfo nicht gefunden oder keine Berechtigung zum Löschen.", "error")
        return redirect(url_for("overview.index", tab="worldinfo"))
    repo.delete(worldinfo_id)
    flash("WorldInfo gelöscht.", "success")
    return redirect(url_for("overview.index", tab="worldinfo"))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_location(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("WorldInfo nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    form = LocationForm.from_request(request.form)
    service = WorldInfoService()
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
            character_id=form.character_id,
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
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("WorldInfo nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    form = LocationForm.from_request(request.form)
    service = WorldInfoService()
    storage = FileStorage()

    loc = repo.get_location(location_id)
    if loc is not None and loc.worldinfo_id == worldinfo_id:
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
                character_id=form.character_id,
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
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("WorldInfo nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    repo.delete_location(location_id)
    flash("Ort gelöscht.", "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))


@worldinfo_bp.route("/<int:worldinfo_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_event(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("WorldInfo nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    form = EventForm.from_request(request.form)
    service = WorldInfoService()
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
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("WorldInfo nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    form = EventForm.from_request(request.form)
    service = WorldInfoService()
    ev = repo.get_event(event_id)
    if ev is not None and ev.worldinfo_id == worldinfo_id:
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
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("WorldInfo nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    repo.delete_event(event_id)
    flash("Event gelöscht.", "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id))
