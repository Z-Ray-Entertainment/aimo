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
    return render_template(
        "chat/select_worldinfo.html",
        character=wrap_dto(char_data),
        worldinfos=wrap_dto(wi_data.get("worldinfos", [])),
        personas=[item["persona"] for item in getattr(g, "persona_items", [])],
        default_persona=getattr(g, "default_persona", None),
    )


@chat_bp.route("/session/<int:session_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def view_session(session_id: int):
    status, data = core_get(f"/api/chat/{session_id}")
    if status != 200 or not data.get("session"):
        flash(tr(_("Chat session not found.")), "error")
        return redirect(url_for("overview.index"))

    chat_session = wrap_dto(data["session"])
    _, char_data = core_get(f"/api/characters/{chat_session.character_id}")
    _, mem_data = core_get(f"/api/chat/{session_id}/memories")
    _, wi_list_data = core_get("/api/worldinfo")
    _, health_data = core_get("/api/admin/health")
    _, sessions_data = core_get("/api/chat/sessions")

    active_wi = None
    if chat_session.active_worldinfo_id:
        wi_code, wi_detail = core_get(f"/api/worldinfo/{chat_session.active_worldinfo_id}")
        if wi_code == 200:
            active_wi = wrap_dto(wi_detail)

    character = wrap_dto(char_data)
    persona_item = next(
        (item for item in getattr(g, "persona_items", []) if item["persona"].id == chat_session.persona_id),
        None,
    )
    persona = persona_item["persona"] if persona_item else getattr(g, "default_persona", None)
    admin_flag = is_admin()
    can_debug = admin_flag or bool(char_data.get("editable"))

    return render_template(
        "chat/session.html",
        chat_session=chat_session,
        character=character,
        persona=persona,
        messages=wrap_dto(data.get("messages", [])),
        memories=wrap_dto(mem_data.get("memories", [])),
        worldinfo=active_wi,
        all_worldinfos=wrap_dto(wi_list_data.get("worldinfos", [])),
        personas=[item["persona"] for item in getattr(g, "persona_items", [])],
        sessions=wrap_dto(sessions_data.get("sessions", [])),
        relationship_tier_name=chat_session.relationship_tier_name,
        image_gen_available=bool(health_data.get("image_gen_enabled") and health_data.get("image_gen_healthy")),
        can_debug_relationship=can_debug,
        can_view_event_counter=can_debug,
        current_user=get_current_user(),
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
