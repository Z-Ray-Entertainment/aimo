from __future__ import annotations

import json

from flask import Response, jsonify, request, stream_with_context

from application.api.auth import get_current_user, require_permission
from application.api.chat import api_chat_bp
from application.api.chat.shared import (
    _BACKGROUND_TASKS,
    _TASKS_LOCK,
    _get_authorized_session,
)
from application.api.helpers import serialize_system_message
from application.chat_services.task_registry import BackgroundTurnTask
from application.chat_services.turn_orchestrator import start_background_turn
from domain.permissions.models import FunctionPermission
from shared.exceptions import AimoError


def _stream_from_task(task: BackgroundTurnTask):
    sent_tokens = 0
    sent_gen_done = False
    sent_image_analyzed = False
    sent_system_message = False

    if task.system_message is not None and not sent_system_message:
        sent_system_message = True
        yield f"event: system_message\ndata: {json.dumps(serialize_system_message(task.system_message))}\n\n"

    while True:
        with task.condition:
            while (
                sent_tokens >= len(task.tokens)
                and (sent_gen_done or not task.generation_done)
                and (sent_image_analyzed or not task.image_analyzed)
                and (sent_system_message or task.system_message is None)
                and task.status not in ("completed", "error", "aborted")
            ):
                task.condition.wait(timeout=15.0)

            emit_sys_msg = task.system_message is not None and not sent_system_message
            if emit_sys_msg:
                sent_system_message = True

            emit_image_analyzed = task.image_analyzed and not sent_image_analyzed
            if emit_image_analyzed:
                sent_image_analyzed = True
            image_alt_text = task.image_alt_text

            new_tokens = list(task.tokens[sent_tokens:])
            sent_tokens = len(task.tokens)
            emit_gen_done = task.generation_done and not sent_gen_done
            if emit_gen_done:
                sent_gen_done = True
            english_reply = task.english_reply
            current_status = task.status
            result_payload = task.result_payload
            error_message = task.error_message

        if emit_sys_msg and task.system_message is not None:
            yield f"event: system_message\ndata: {json.dumps(serialize_system_message(task.system_message))}\n\n"

        if emit_image_analyzed:
            yield f"event: image_analyzed\ndata: {json.dumps({'image_alt_text': image_alt_text or '', 'user_message_idx': task.user_message_idx})}\n\n"

        for tok_data in new_tokens:
            yield f"event: token\ndata: {json.dumps(tok_data)}\n\n"

        if emit_gen_done:
            yield f"event: generation_done\ndata: {json.dumps({'english_content': english_reply})}\n\n"

        if current_status == "aborted" or task.is_aborted:
            task.delivered_via_stream = True
            yield f"event: aborted\ndata: {json.dumps({'error': error_message or 'Generation aborted by user'})}\n\n"
            break

        if current_status == "error":
            task.delivered_via_stream = True
            yield f"event: error\ndata: {json.dumps({'error': error_message or 'Generation error'})}\n\n"
            break

        if current_status == "completed" and result_payload is not None:
            task.delivered_via_stream = True
            yield f"event: message_complete\ndata: {json.dumps(result_payload)}\n\n"
            break


@api_chat_bp.route("/<int:session_id>/messages", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def post_message(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin_flag = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    if request.is_json:
        data = request.get_json(silent=True) or {}
        user_text = str(data.get("message", "")).strip()
        user_lang = str(data.get("language", user.language or "en")).strip()
        stream_now = bool(data.get("stream", True))
        uploaded_file = None
    else:
        user_text = str(request.form.get("message", "")).strip()
        user_lang = str(request.form.get("language", user.language or "en")).strip()
        stream_now = request.form.get("stream", "true").lower() == "true"
        uploaded_file = request.files.get("image")

    if not user_text and not uploaded_file:
        return jsonify({"error": "Message or image is required."}), 400

    try:
        task, user_msg, triggered_event = start_background_turn(
            session_id=session_id,
            user_text=user_text,
            user_language=user_lang,
            uploaded_image_file=uploaded_file,
            is_admin=is_admin_flag,
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400

    if not stream_now:
        return jsonify(
            {
                "status": "ready_for_stream",
                "task_id": task.task_id,
                "has_image": task.has_image,
                "user_message": {
                    "id": user_msg.id,
                    "message_idx": user_msg.message_idx,
                    "content": user_msg.content,
                    "localized_content": user_msg.content,
                    "image_path": user_msg.image_path,
                    "image_alt_text": user_msg.image_alt_text,
                },
                "triggered_event": triggered_event,
                "system_message": (
                    serialize_system_message(task.system_message)
                    if task.system_message is not None
                    else None
                ),
                "cooldown_counter": task.cooldown_counter if task.can_view_event_counter else None,
                "events_enabled": task.events_enabled,
            }
        )

    return Response(
        stream_with_context(_stream_from_task(task)),
        content_type="text/event-stream; charset=utf-8",
    )


@api_chat_bp.route("/<int:session_id>/stream", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def stream_session_response(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, is_admin_flag = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    user_lang = request.args.get("language", user.language or "en")
    msg_text = request.args.get("message", "").strip()

    if msg_text:
        try:
            task, _, _ = start_background_turn(
                session_id=session_id,
                user_text=msg_text,
                user_language=user_lang,
                is_admin=is_admin_flag,
            )
        except AimoError as exc:
            return jsonify({"error": str(exc)}), 400
    else:
        with _TASKS_LOCK:
            task = _BACKGROUND_TASKS.get(session_id)
        if task is None or (task.status in ("completed", "error") and task.delivered_via_stream):
            return jsonify({"error": "No pending message for stream."}), 400

    return Response(
        stream_with_context(_stream_from_task(task)),
        content_type="text/event-stream; charset=utf-8",
    )


@api_chat_bp.route("/<int:session_id>/status", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def get_session_generation_status(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    with _TASKS_LOCK:
        task = _BACKGROUND_TASKS.get(session_id)

    if task is None:
        return jsonify({"active": False, "status": "idle"})

    with task.condition:
        is_active = task.status in ("analyzing_image", "thinking", "streaming", "translating")
        return jsonify(
            {
                "active": is_active,
                "task_id": task.task_id,
                "status": task.status,
                "has_image": task.has_image,
            }
        )


@api_chat_bp.route("/<int:session_id>/abort", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def abort_generation(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    chat_session, _ = _get_authorized_session(session_id, user)
    if chat_session is None:
        return jsonify({"error": "Session not found."}), 404

    with _TASKS_LOCK:
        task = _BACKGROUND_TASKS.get(session_id)

    if task is None:
        return jsonify({"aborted": False, "message": "No active turn."})

    with task.condition:
        if task.status in ("analyzing_image", "thinking", "streaming", "translating"):
            task.is_aborted = True
            task.status = "aborted"
            task.error_message = "Generation aborted by user"
            task.condition.notify_all()
            return jsonify({"aborted": True})

    return jsonify({"aborted": False, "status": task.status if task else "idle"})
