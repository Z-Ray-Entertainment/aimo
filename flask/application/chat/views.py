from flask import flash, g, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_permission
from application.chat import chat_bp
from application.core_client import core_delete, core_get, core_post, core_put
from application.ui_helpers import tr
from application.view_models import FunctionPermission, wrap_dto
from i18n import gettext_noop as _


@chat_bp.route("/character/<int:character_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def open_character_chat(character_id: int):
    status, data = core_get("/api/chat/sessions")
    sessions = [s for s in wrap_dto(data.get("sessions", [])) if s.character_id == character_id] if status == 200 else []
    if sessions:
        return redirect(url_for("chat.view_session", session_id=sessions[0].id))
    return redirect(url_for("chat.new_character_chat", character_id=character_id))


@chat_bp.route("/character/<int:character_id>/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def new_character_chat(character_id: int):
    user = get_current_user()
    _, char_data = core_get(f"/api/characters/{character_id}")
    if not char_data.get("id"):
        flash(tr(_("Character not found.")), "error")
        return redirect(url_for("overview.index"))

    if request.method == "POST":
        persona_id = request.form.get("persona_id") or (g.default_persona.id if getattr(g, "default_persona", None) else None)
        worldinfo_id = request.form.get("worldinfo_id") or None
        status, payload = core_post(
            "/api/chat/sessions",
            json={
                "character_id": character_id,
                "persona_id": persona_id,
                "worldinfo_id": worldinfo_id,
            },
        )
        if status < 400 and payload.get("id"):
            return redirect(url_for("chat.view_session", session_id=payload["id"]))
        flash(payload.get("error") or tr(_("Failed to start chat session.")), "error")
        return redirect(url_for("overview.index"))

    _, wi_data = core_get("/api/worldinfo")
    _, setup_data = core_get(f"/api/chat/character/{character_id}/setup")
    character = wrap_dto(char_data)
    worldinfos = wrap_dto(wi_data.get("worldinfos", []))

    return render_template(
        "chat/select_worldinfo.html",
        character=character,
        worldinfos=worldinfos,
        personas=[item["persona"] for item in getattr(g, "persona_items", [])],
        default_persona=getattr(g, "default_persona", None),
        lorebook_data=setup_data.get("lorebook_data", {}),
        worldinfo_lorebooks_map=setup_data.get("worldinfo_lorebooks_map", {}),
        worldinfo_names_map=setup_data.get("worldinfo_names_map", {}),
        character_lorebook_world_conditions=getattr(character, "lorebook_world_conditions", {}) or {},
    )


@chat_bp.route("/session/<int:session_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def view_session(session_id: int):
    user = get_current_user()
    status, data = core_get(f"/api/chat/{session_id}")
    if status != 200 or not data.get("session"):
        flash(tr(_("Chat session not found.")), "error")
        return redirect(url_for("overview.index"))

    chat_session = wrap_dto(data["session"])
    _, char_data = core_get(f"/api/characters/{chat_session.character_id}")
    _, mem_data = core_get(f"/api/chat/{session_id}/memories")
    _, wi_list_data = core_get("/api/worldinfo")
    _, tiers_data = core_get("/api/characters/relationship-tiers")
    _, health_data = core_get("/api/admin/health")
    _, sessions_data = core_get("/api/chat/sessions")

    active_wi = None
    if chat_session.active_worldinfo_id:
        wi_code, wi_detail = core_get(f"/api/worldinfo/{chat_session.active_worldinfo_id}")
        if wi_code == 200:
            active_wi = wrap_dto(wi_detail)

    character = wrap_dto(char_data)
    all_worldinfos = wrap_dto(wi_list_data.get("worldinfos", []))
    persona_items = getattr(g, "persona_items", [])
    persona_item = next(
        (item for item in persona_items if item["persona"].id == chat_session.persona_id),
        None,
    )
    persona = persona_item["persona"] if persona_item else getattr(g, "default_persona", None)
    user_personas = [item["persona"] for item in persona_items]
    admin_flag = is_admin()
    can_debug = admin_flag or bool(char_data.get("editable"))

    messages = wrap_dto(data.get("messages", []))
    worldinfo_locations = list(getattr(active_wi, "locations", []) or []) if active_wi else []
    worldinfo_events = list(getattr(active_wi, "events", []) or []) if active_wi else []
    current_location = next(
        (loc for loc in worldinfo_locations if loc.id == getattr(chat_session, "current_location_id", None)),
        None,
    )
    initial_location = next(
        (loc for loc in worldinfo_locations if loc.id == getattr(character, "initial_location_id", None)),
        None,
    )
    character_events = list(getattr(character, "events", []) or [])
    rel_score = float(getattr(chat_session, "relationship_value", 0.0) or 0.0)
    unlocked_gallery = [
        img
        for img in (getattr(character, "gallery_images", []) or [])
        if getattr(img, "unlock_threshold", 0) <= rel_score
    ]
    active_sprite = next(
        (sp for sp in (getattr(character, "sprites", []) or []) if sp.emotion == "neutral"),
        None,
    )
    session_media_images = [m.image_path for m in messages if getattr(m, "image_path", None)]
    gallery_threshold_names = {t.level: t.name for t in wrap_dto(tiers_data.get("tiers", []))}
    lorebook_data = data.get("lorebook_data", {})
    all_sessions = wrap_dto(sessions_data.get("sessions", []))
    image_gen_available = bool(health_data.get("image_gen_enabled") and health_data.get("image_gen_healthy"))

    return render_template(
        "chat/session.html",
        chat_session=chat_session,
        character=character,
        persona=persona,
        persona_i18n_description=persona_item.get("i18n_description", {}) if persona_item else {},
        persona_i18n_appearance=persona_item.get("i18n_appearance", {}) if persona_item else {},
        user_personas=user_personas,
        personas=user_personas,
        all_sessions=all_sessions,
        sessions=all_sessions,
        messages=messages,
        memories=wrap_dto(mem_data.get("memories", [])),
        lorebook_data=lorebook_data,
        worldinfo=active_wi,
        current_location=current_location,
        initial_location=initial_location,
        worldinfo_locations=worldinfo_locations,
        worldinfo_events=worldinfo_events,
        character_events=character_events,
        all_worldinfos=all_worldinfos,
        active_sprite=active_sprite,
        unlocked_gallery=unlocked_gallery,
        session_media_images=session_media_images,
        sys_lang=getattr(g, "ui_language", "en"),
        relationship_tier_name=chat_session.relationship_tier_name,
        gallery_threshold_names=gallery_threshold_names,
        image_gen_available=image_gen_available,
        comfyui_available=image_gen_available,
        is_admin=admin_flag,
        can_debug_relationship=can_debug,
        can_view_event_counter=can_debug,
        active_tab=request.args.get("tab", "messages"),
        current_user=user,
    )


@chat_bp.route("/session/<int:session_id>/update-settings", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def update_session_settings(session_id: int):
    body: dict = {}
    if "persona_id" in request.form and request.form["persona_id"]:
        body["persona_id"] = int(request.form["persona_id"])
    if "worldinfo_id" in request.form:
        body["active_worldinfo_id"] = request.form["worldinfo_id"] or None
    if "events_enabled" in request.form:
        body["events_enabled"] = request.form["events_enabled"].lower() in ("1", "true", "on", "yes")
    if "thinking_enabled" in request.form:
        body["thinking_enabled"] = request.form["thinking_enabled"].lower() in ("1", "true", "on", "yes")
    if request.form.get("reset_relationship"):
        body["reset_relationship"] = True

    status, payload = core_put(f"/api/chat/{session_id}", json=body)
    if status < 400:
        flash(tr(_("Session settings updated.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to update session settings.")), "error")
    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_session(session_id: int):
    status, payload = core_delete(f"/api/chat/{session_id}")
    if status < 400:
        flash(tr(_("Chat session deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Chat session not found.")), "error")
    return redirect(url_for("overview.index"))
