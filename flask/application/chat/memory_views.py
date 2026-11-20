from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, has_perm, is_admin as is_admin_user, require_permission
from application.chat.forms import MemoryEditForm, StartChatForm
from application.translation_helpers import is_worldinfo_ready_for_language
from application.ui_helpers import tr
from i18n import gettext_noop as _
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.chat.models import MessageRole
from domain.chat.services import ChatService
from domain.memories.services import MemoryService
from domain.permissions.models import FunctionPermission
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from shared.exceptions import AimoError
from shared.utils import replace_roleplay_placeholders

from application.chat import chat_bp


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def edit_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or (chat_session.user_id != user.id and not user.is_initial_admin):
        return redirect(url_for("overview.index"))

    mem_repo = MemoryRepository()
    mem_service = MemoryService()
    form = MemoryEditForm.from_request(request.form)

    mem = mem_repo.get_by_id(memory_id)
    if mem is not None and mem.chat_session_id == session_id:
        try:
            mem_service.update_memory(
                memory=mem,
                title=form.title,
                tags=form.tags,
                summary=form.summary,
            )
            mem_repo.update_memory(mem)
            flash(tr(_("Memory updated.")), "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or (chat_session.user_id != user.id and not user.is_initial_admin):
        return redirect(url_for("overview.index"))

    mem_repo = MemoryRepository()
    mem = mem_repo.get_by_id(memory_id)
    if mem is not None and mem.chat_session_id == session_id:
        mem_repo.delete_memory(memory_id)
        flash(tr(_("Memory deleted.")), "success")
    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/recalculate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def recalculate_memory(session_id: int, memory_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    settings_repo = SettingsRepository()
    mem_service = MemoryService()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or (chat_session.user_id != user.id and not user.is_initial_admin):
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": "Session not found."}, 404
        flash(tr(_("Chat session not found.")), "error")
        return redirect(url_for("overview.index"))

    target_memory = mem_repo.get_by_id(memory_id)
    if target_memory is None or target_memory.chat_session_id != session_id:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": "Memory not found."}, 404
        flash(tr(_("Memory not found.")), "error")
        return redirect(url_for("chat.view_session", session_id=session_id))

    all_messages = chat_repo.get_messages(session_id, limit=None)
    narrative_msgs = mem_service.filter_narrative_messages(all_messages)
    all_memories = mem_repo.list_for_session(session_id)

    chunk = mem_service.extract_messages_for_memory(
        memories=all_memories,
        target_memory=target_memory,
        all_narrative_messages=narrative_msgs,
        chunk_size=10,
    )
    if not chunk:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": "No narrative messages found for this memory episode."}, 400
        flash(tr(_("No messages found for this memory episode.")), "error")
        return redirect(url_for("chat.view_session", session_id=session_id))

    try:
        settings = settings_repo.get_settings()
        llm = get_llm_provider(settings)
        msg_dicts = [
            {"role": m.role.value, "content": m.english_content or m.localized_content or ""}
            for m in chunk
        ]
        title, tags, summary, _ = mem_service.extract_memory_and_title(
            last_10_messages=msg_dicts,
            memory_prompt=settings.prompts.memory_prompt,
            llm_provider=llm,
            model=settings.tasks.memory_model,
            params=settings.params,
        )
        mem_service.update_memory(
            memory=target_memory,
            title=title,
            tags=tags,
            summary=summary,
        )
        mem_repo.update_memory(target_memory)
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {
                "id": target_memory.id,
                "title": target_memory.title,
                "tags": target_memory.tags,
                "summary": target_memory.summary,
            }
        flash(tr(_("Memory recalculated successfully.")), "success")
    except Exception as exc:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": str(exc)}, 500
        flash(tr(_("Recalculation error: %(error)s"), error=exc), "error")

    return redirect(url_for("chat.view_session", session_id=session_id))

