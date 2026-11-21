from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_auth, require_permission
from application.ui_helpers import tr
from application.worldinfo.forms import EventForm, LocationForm
from i18n import gettext_noop as _
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
        flash(tr(_("WorldInfo '%(name)s' created."), name=saved.name), "success")
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
    if worldinfo is None or not worldinfo.is_visible_to_user(user.id, is_admin()):
        flash(tr(_("WorldInfo not found.")), "error")
        return redirect(url_for("overview.index"))

    is_editable = worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag)
    is_author = (worldinfo.user_id == user.id or is_admin())

    if request.method == "POST":
        if not is_editable:
            flash(tr(_("Access denied: You can only edit your own WorldInfos or creations shared with you.")), "error")
            return redirect(url_for("overview.index"))
        try:
            storage = FileStorage()
            cover_path = worldinfo.cover_image_path
            cover_file = request.files.get("cover_file")
            if cover_file and cover_file.filename:
                cover_path = storage.save_cover(cover_file.stream, cover_file.filename)

            backdrop_path = worldinfo.backdrop_image_path
            if request.form.get("remove_backdrop") == "1":
                backdrop_path = None
            backdrop_file = request.files.get("backdrop_file")
            if backdrop_file and backdrop_file.filename:
                backdrop_path = storage.save_background(backdrop_file.stream, backdrop_file.filename)

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
                backdrop_image_path=backdrop_path,
                lorebook_id=lb_id,
                collaborator_creator_tags=collaborator_tags,
                is_proper_noun=bool(request.form.get("is_proper_noun")),
            )
            worldinfo = repo.update(worldinfo)
            flash(tr(_("WorldInfo saved.")), "success")
            active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
            if active_tab not in ("info", "places", "events", "collab"):
                active_tab = "info"
            return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo.id, tab=active_tab))
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
    user_lang = (user.language or "en")[:2].lower()
    if not is_editable:
        from application.translation_helpers import is_worldinfo_ready_for_language

        if not is_worldinfo_ready_for_language(worldinfo, user_lang, trans_repo, repo):
            flash(tr(_("This world is not yet available in your language.")), "warning")
            return redirect(url_for("overview.index", tab="worldinfo"))
        for loc in locations:
            if loc.id is not None:
                if not getattr(loc, "is_proper_noun", False):
                    loc.name = trans_repo.get_localized_field("worldinfo_location", loc.id, "name", user_lang, loc.name)
                loc.description = trans_repo.get_localized_field(
                    "worldinfo_location", loc.id, "description", user_lang, loc.description
                )
                raw_tags = trans_repo.get_localized_field("worldinfo_location", loc.id, "tags", user_lang, "")
                if raw_tags:
                    loc.tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        for ev in events:
            if ev.id is not None:
                if not getattr(ev, "is_proper_noun", False):
                    ev.title = trans_repo.get_localized_field("worldinfo_event", ev.id, "title", user_lang, ev.title)
                ev.description = trans_repo.get_localized_field(
                    "worldinfo_event", ev.id, "description", user_lang, ev.description
                )

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

    loc_display = {
        loc.id: {
            "name": (
                loc.name
                if getattr(loc, "is_proper_noun", False)
                else trans_repo.get_localized_field("worldinfo_location", loc.id, "name", user_lang, loc.name)
            ),
            "description": trans_repo.get_localized_field(
                "worldinfo_location", loc.id, "description", user_lang, loc.description
            ),
        }
        for loc in locations
        if loc.id is not None
    }
    ev_display = {
        ev.id: {
            "title": (
                ev.title
                if getattr(ev, "is_proper_noun", False)
                else trans_repo.get_localized_field("worldinfo_event", ev.id, "title", user_lang, ev.title)
            ),
            "description": trans_repo.get_localized_field(
                "worldinfo_event", ev.id, "description", user_lang, ev.description
            ),
        }
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
        loc_display=loc_display,
        ev_display=ev_display,
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
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        flash(tr(_("WorldInfo not found.")), "error")
        return redirect(url_for("overview.index", tab="worldinfo"))
    if not orig.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        from application.translation_helpers import is_worldinfo_ready_for_language

        trans_repo = TranslationRepository()
        user_lang = (user.language or "en")[:2].lower()
        if not is_worldinfo_ready_for_language(orig, user_lang, trans_repo, repo):
            flash(tr(_("This world is not yet available in your language.")), "warning")
            return redirect(url_for("overview.index", tab="worldinfo"))
    copied = repo.duplicate(worldinfo_id, user.id)
    flash(tr(_("Copy '%(name)s' created successfully."), name=copied.name), "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=copied.id))


@worldinfo_bp.route("/<int:worldinfo_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_DELETE)
def delete_worldinfo(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_deletable_by_user(user.id, is_admin()):
        flash(tr(_("WorldInfo not found or no permission to delete.")), "error")
        return redirect(url_for("overview.index", tab="worldinfo"))
    repo.delete(worldinfo_id)
    flash(tr(_("WorldInfo deleted.")), "success")
    return redirect(url_for("overview.index", tab="worldinfo"))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_location(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("WorldInfo not found or no permission.")), "error")
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
            is_proper_noun=form.is_proper_noun,
        )
        saved_loc = repo.add_location(loc)
        TranslationRepository().save_field_variants_json(
            "worldinfo_location", saved_loc.id, "description", request.form.get("i18n_description")
        )
        flash(tr(_("Location '%(name)s' created."), name=loc.name), "success")
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="places"))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/<int:location_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def edit_location(worldinfo_id: int, location_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("WorldInfo not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    form = LocationForm.from_request(request.form)
    service = WorldInfoService()
    storage = FileStorage()

    loc = repo.get_location(location_id)
    if loc is not None and loc.worldinfo_id == worldinfo_id:
        try:
            bg_path = form.background_image_path or loc.background_image_path
            if request.form.get("remove_background") == "1":
                bg_path = None
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
                is_proper_noun=form.is_proper_noun,
            )
            repo.update_location(loc)
            TranslationRepository().save_field_variants_json(
                "worldinfo_location", loc.id, "description", request.form.get("i18n_description")
            )
            flash(tr(_("Location updated.")), "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="places"))


@worldinfo_bp.route("/<int:worldinfo_id>/locations/<int:location_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def delete_location(worldinfo_id: int, location_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("WorldInfo not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    repo.delete_location(location_id)
    flash(tr(_("Location deleted.")), "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="places"))


@worldinfo_bp.route("/<int:worldinfo_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def add_event(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("WorldInfo not found or no permission.")), "error")
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
            is_proper_noun=form.is_proper_noun,
        )
        saved_ev = repo.add_event(ev)
        trans_repo = TranslationRepository()
        trans_repo.save_field_variants_json(
            "worldinfo_event", saved_ev.id, "title", request.form.get("i18n_title")
        )
        trans_repo.save_field_variants_json(
            "worldinfo_event", saved_ev.id, "description", request.form.get("i18n_description")
        )
        flash(tr(_("Event '%(title)s' added."), title=ev.title), "success")
    except AimoError as exc:
        flash(str(exc), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="events"))


@worldinfo_bp.route("/<int:worldinfo_id>/events/<int:event_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def edit_event(worldinfo_id: int, event_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("WorldInfo not found or no permission.")), "error")
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
                is_proper_noun=form.is_proper_noun,
            )
            repo.update_event(ev)
            trans_repo = TranslationRepository()
            trans_repo.save_field_variants_json(
                "worldinfo_event", ev.id, "title", request.form.get("i18n_title")
            )
            trans_repo.save_field_variants_json(
                "worldinfo_event", ev.id, "description", request.form.get("i18n_description")
            )
            flash(tr(_("Event updated.")), "success")
        except AimoError as exc:
            flash(str(exc), "error")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="events"))


@worldinfo_bp.route("/<int:worldinfo_id>/events/<int:event_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def delete_event(worldinfo_id: int, event_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    worldinfo = repo.get_by_id(worldinfo_id)
    if worldinfo is None or not worldinfo.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("WorldInfo not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    repo.delete_event(event_id)
    flash(tr(_("Event deleted.")), "success")
    return redirect(url_for("worldinfo.detail", worldinfo_id=worldinfo_id, tab="events"))
