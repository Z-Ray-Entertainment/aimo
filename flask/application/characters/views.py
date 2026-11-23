import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_auth, require_permission
from application.characters.forms import CharacterForm
from application.core_client import core_delete, core_get, core_post, core_put
from application.ui_helpers import notify_author_translation_hint, tr
from application.view_models import Emotion, FunctionPermission, Gender, wrap_dto
from i18n import gettext_noop as _

characters_bp = Blueprint("characters", __name__, url_prefix="/characters")

_VALID_CHARACTER_TABS = {"info", "gallery", "sprites", "dialogue", "world", "events", "lorebooks", "collab"}


def _form_from_character(char) -> CharacterForm:
    tags = list(getattr(char, "collaborator_creator_tags", []) or [])
    return CharacterForm(
        name=getattr(char, "name", "") or "",
        gender=getattr(char, "gender", "non-binary") or "non-binary",
        visibility=getattr(char, "visibility", "private") or "private",
        appearance=getattr(char, "appearance", "") or "",
        description=getattr(char, "description", "") or "",
        dialogue_examples=list(getattr(char, "dialogue_examples", []) or []),
        first_message=getattr(char, "first_message", "") or "",
        suggested_worldinfo_id=getattr(char, "suggested_worldinfo_id", None),
        initial_location_id=getattr(char, "initial_location_id", None),
        initial_relationship=int(getattr(char, "initial_relationship", 0) or 0),
        linked_lorebook_ids=list(getattr(char, "linked_lorebook_ids", []) or []),
        lorebook_world_conditions={
            int(k): int(v) for k, v in (getattr(char, "lorebook_world_conditions", {}) or {}).items()
        },
        preferred_location_ids=list(getattr(char, "preferred_location_ids", []) or []),
        disliked_location_ids=list(getattr(char, "disliked_location_ids", []) or []),
        collaborator_creator_tags=tags,
        collaborator_creator_tags_text=", ".join(tags),
    )


def _render_creator(
    character=None,
    form: CharacterForm | None = None,
    is_author: bool = True,
    is_editable: bool = True,
    active_tab: str = "info",
    char_translations: dict | None = None,
):
    if active_tab not in _VALID_CHARACTER_TABS:
        active_tab = "info"

    _, lb_data = core_get("/api/lorebooks")
    _, wi_data = core_get("/api/worldinfo")
    _, tiers_data = core_get("/api/characters/relationship-tiers")

    lorebooks = wrap_dto(lb_data.get("lorebooks", []))
    worldinfos = wrap_dto(wi_data.get("worldinfos", []))
    rel_tiers = wrap_dto(tiers_data.get("tiers", []))
    gallery_threshold_names = {t.level: t.name for t in rel_tiers}

    world_map = {w.id: w for w in worldinfos}
    ordered_worldinfos = list(worldinfos)
    all_locations = []
    locations_by_world: dict[int, list] = {}
    for w in worldinfos:
        locs = list(getattr(w, "locations", []) or [])
        locations_by_world[w.id] = locs
        all_locations.extend(locs)

    suggested_wi_id = getattr(character, "suggested_worldinfo_id", None) if character else None
    event_locations = locations_by_world.get(suggested_wi_id, []) if suggested_wi_id else []
    loc_map = {loc.id: loc for loc in all_locations if getattr(loc, "id", None) is not None}

    raw_sprites: dict[str, list] = {}
    if character is not None:
        for sp in getattr(character, "sprites", []) or []:
            raw_sprites.setdefault(sp.emotion, []).append(sp)

    all_emotions = [e.value for e in Emotion]
    ordered_emotions = ["neutral"] + [em for em in all_emotions if em != "neutral"]
    sprite_by_emotion = {
        em: raw_sprites[em][0]
        for em in ordered_emotions
        if em in raw_sprites and raw_sprites[em]
    }
    available_emotions = [em for em in ordered_emotions if em not in sprite_by_emotion]

    character_events = wrap_dto(getattr(character, "events", []) or []) if character else []
    loc_display = {loc.id: {"name": loc.name} for loc in event_locations if getattr(loc, "id", None) is not None}
    ev_display = {
        ev.id: {"title": ev.title, "description": ev.description}
        for ev in character_events
        if getattr(ev, "id", None) is not None
    }

    return render_template(
        "characters/creator.html",
        character=character,
        form=form or CharacterForm(),
        is_author=is_author,
        is_editable=is_editable,
        genders=[g.value for g in Gender],
        emotions=all_emotions,
        lorebooks=lorebooks,
        worldinfos=worldinfos,
        ordered_worldinfos=ordered_worldinfos,
        world_map=world_map,
        all_locations=all_locations,
        event_locations=event_locations,
        loc_map=loc_map,
        loc_display=loc_display,
        ev_display=ev_display,
        locations_by_world=locations_by_world,
        events=character_events,
        ev_translations={},
        event_translations={},
        char_translations=char_translations or {},
        sprite_by_emotion=sprite_by_emotion,
        available_emotions=available_emotions,
        relationship_tiers=rel_tiers,
        gallery_threshold_names=gallery_threshold_names,
        active_tab=active_tab,
    )


@characters_bp.route("/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def new_character():
    if request.method == "POST":
        form = CharacterForm.from_request(request.form)
        files = {}
        for key in ("primary_portrait", "avatar_portrait", "card_portrait"):
            f = request.files.get(key)
            if f and f.filename:
                files[key] = (f.filename, f.stream, f.mimetype or "application/octet-stream")
        user = get_current_user()
        origin_language = (getattr(user, "language", None) or "en")[:2].lower()
        form_data = {
            "name": form.name,
            "gender": form.gender,
            "description": form.description,
            "appearance": form.appearance,
            "first_message": form.first_message,
            "visibility": form.visibility,
            "origin_language": origin_language,
            "i18n_description": request.form.get("i18n_description", ""),
            "i18n_appearance": request.form.get("i18n_appearance", ""),
            "i18n_first_message": request.form.get("i18n_first_message", ""),
            "dialogue_examples_json": json.dumps(form.dialogue_examples),
            "linked_lorebook_ids": [str(x) for x in form.linked_lorebook_ids],
            "lorebook_world_conditions_json": json.dumps({str(k): v for k, v in form.lorebook_world_conditions.items()}),
            "preferred_location_ids": [str(x) for x in form.preferred_location_ids],
            "disliked_location_ids": [str(x) for x in form.disliked_location_ids],
            "collaborator_creator_tags": form.collaborator_creator_tags_text,
            "initial_relationship": str(form.initial_relationship),
            "suggested_worldinfo_id": str(form.suggested_worldinfo_id or ""),
            "initial_location_id": str(form.initial_location_id or ""),
        }
        status, payload = core_post("/api/characters", data=form_data, files=files or None)
        if status < 400 and payload.get("id"):
            notify_author_translation_hint("character", int(payload["id"]), "description")
            flash(tr(_("Character '%(name)s' created."), name=payload.get("name", form.name)), "success")
            return redirect(url_for("characters.edit_character", character_id=payload["id"]))
        flash(payload.get("error") or tr(_("Failed to create character.")), "error")
        return redirect(url_for("overview.index"))

    return _render_creator(
        character=None,
        form=CharacterForm(),
        is_author=True,
        is_editable=True,
        active_tab=request.args.get("tab", "info"),
    )


@characters_bp.route("/<int:character_id>", methods=["GET"])
@characters_bp.route("/<int:character_id>/edit", methods=["GET", "POST"])
@require_auth
def edit_character(character_id: int):
    status, data = core_get(f"/api/characters/{character_id}")
    if status != 200:
        flash(tr(_("Character not found.")), "error")
        return redirect(url_for("overview.index"))

    char = wrap_dto(data)
    is_editable = bool(data.get("editable"))
    is_author = is_admin() or (get_current_user() and data.get("user_id") == get_current_user().id)
    active_tab = request.form.get("active_tab") or request.args.get("tab", "info")

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
                "dialogue_examples": form.dialogue_examples,
                "linked_lorebook_ids": form.linked_lorebook_ids,
                "lorebook_world_conditions": {str(k): v for k, v in form.lorebook_world_conditions.items()},
                "suggested_worldinfo_id": form.suggested_worldinfo_id,
                "initial_location_id": form.initial_location_id,
                "preferred_location_ids": form.preferred_location_ids,
                "disliked_location_ids": form.disliked_location_ids,
                "collaborator_creator_tags": form.collaborator_creator_tags,
                "i18n_description": request.form.get("i18n_description", ""),
                "i18n_appearance": request.form.get("i18n_appearance", ""),
                "i18n_first_message": request.form.get("i18n_first_message", ""),
            },
        )
        if upd_status < 400:
            notify_author_translation_hint("character", character_id, "description")
            flash(tr(_("Character updated.")), "success")
            return redirect(url_for("characters.edit_character", character_id=character_id, tab=active_tab))
        flash(upd_data.get("error") or tr(_("Failed to update character.")), "error")
    else:
        form = _form_from_character(char)

    return _render_creator(
        character=char,
        form=form,
        is_author=bool(is_author),
        is_editable=is_editable,
        active_tab=active_tab,
        char_translations=data.get("i18n", {}) or {},
    )


@characters_bp.route("/<int:character_id>/copy", methods=["POST"])
@characters_bp.route("/<int:character_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def copy_character(character_id: int):
    status, payload = core_post(f"/api/characters/{character_id}/duplicate")
    if status < 400 and payload.get("id"):
        flash(tr(_("Character copied as '%(name)s'."), name=payload.get("name", "")), "success")
        return redirect(url_for("characters.edit_character", character_id=payload["id"]))
    flash(payload.get("error") or tr(_("Character not found.")), "error")
    return redirect(url_for("overview.index"))


@characters_bp.route("/<int:character_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_DELETE)
def delete_character(character_id: int):
    status, payload = core_delete(f"/api/characters/{character_id}")
    if status < 400:
        flash(tr(_("Character deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Character not found.")), "error")
    return redirect(url_for("overview.index"))


from application.characters import sub_views as _sub_views  # noqa: E402, F401
