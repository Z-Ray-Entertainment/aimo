from flask import flash, redirect, request, url_for

from application.auth.decorators import require_permission
from application.chat.forms import MemoryEditForm
from application.chat import chat_bp
from application.core_client import core_delete, core_post, core_put
from application.ui_helpers import tr
from application.view_models import FunctionPermission
from i18n import gettext_noop as _


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def edit_memory(session_id: int, memory_id: int):
    form = MemoryEditForm.from_request(request.form)
    status, payload = core_put(
        f"/api/chat/{session_id}/memories/{memory_id}",
        json={"title": form.title, "tags": form.tags, "summary": form.summary},
    )
    if status < 400:
        flash(tr(_("Memory updated.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to update memory.")), "error")
    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_memory(session_id: int, memory_id: int):
    status, payload = core_delete(f"/api/chat/{session_id}/memories/{memory_id}")
    if status < 400:
        flash(tr(_("Memory deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete memory.")), "error")
    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/recalculate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def recalculate_memory(session_id: int, memory_id: int):
    status, payload = core_post(f"/api/chat/{session_id}/memories/{memory_id}/recalculate")
    if status < 400:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return payload
        flash(tr(_("Memory recalculated successfully.")), "success")
    else:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return payload or {"error": "Memory recalculation failed."}, status
        flash(payload.get("error") or tr(_("Recalculation failed.")), "error")
    return redirect(url_for("chat.view_session", session_id=session_id))
