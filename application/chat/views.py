from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_permission
from application.chat.forms import MemoryEditForm, StartChatForm
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.chat.services import ChatService
from domain.memories.services import MemoryService
from domain.permissions.models import FunctionPermission
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.chat_repository import ChatRepository
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from shared.exceptions import AimoError

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("/character/<int:character_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def open_character_chat(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    char_repo = CharacterRepository()

    character = char_repo.get_by_id(character_id)
    if character is None:
        flash("Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    sessions = chat_repo.list_sessions_for_character(character_id, user.id)
    if sessions and not request.args.get("new"):
        return redirect(url_for("chat.view_session", session_id=sessions[0].id))

    return redirect(url_for("chat.new_character_chat", character_id=character_id))


@chat_bp.route("/character/<int:character_id>/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def new_character_chat(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    chat_repo = ChatRepository()
    chat_service = ChatService()

    character = char_repo.get_by_id(character_id)
    if character is None:
        flash("Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    personas = persona_repo.list_for_user(user.id)
    if not personas:
        persona_service = PersonaService()
        fallback_p = persona_service.create_persona(
            user_id=user.id,
            name=user.username,
            gender=Gender.NON_BINARY,
            portrait_path="portraits/default_persona.png",
            description="Abenteurer.",
            appearance="Reisender.",
            is_default=True,
        )
        personas = [persona_repo.create(fallback_p)]

    worldinfos = wi_repo.list_all()

    if request.method == "POST":
        form = StartChatForm.from_request(request.form)
        selected_persona_id = form.persona_id or (personas[0].id or 0)
        try:
            session_obj, first_msg = chat_service.create_session(
                user_id=user.id,
                character=character,
                persona_id=selected_persona_id,
                worldinfo_id=form.worldinfo_id,
                title=form.title or None,
            )
            saved_session = chat_repo.create_session(session_obj)
            assert saved_session.id is not None
            first_msg.session_id = saved_session.id
            chat_repo.add_message(first_msg)
            return redirect(url_for("chat.view_session", session_id=saved_session.id))
        except AimoError as exc:
            flash(str(exc), "error")

    default_persona = next((p for p in personas if p.is_default), personas[0])

    if len(personas) == 1 and not worldinfos and not request.args.get("configure"):
        session_obj, first_msg = chat_service.create_session(
            user_id=user.id,
            character=character,
            persona_id=default_persona.id or 0,
            worldinfo_id=None,
        )
        saved_session = chat_repo.create_session(session_obj)
        assert saved_session.id is not None
        first_msg.session_id = saved_session.id
        chat_repo.add_message(first_msg)
        return redirect(url_for("chat.view_session", session_id=saved_session.id))

    return render_template(
        "chat/select_worldinfo.html",
        character=character,
        personas=personas,
        default_persona=default_persona,
        worldinfos=worldinfos,
    )


@chat_bp.route("/session/<int:session_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def view_session(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    mem_repo = MemoryRepository()

    chat_service = ChatService()
    char_service = CharacterService()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or chat_session.user_id != user.id:
        flash("Chat-Session nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    chat_service.apply_time_decay(chat_session)
    chat_repo.update_session(chat_session)

    character = char_repo.get_by_id(chat_session.character_id)
    if character is None:
        flash("Zugehöriger Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    persona = persona_repo.get_by_id(chat_session.persona_id)
    user_personas = persona_repo.list_for_user(user.id)
    all_sessions = chat_repo.list_sessions_for_character(character.id or 0, user.id)
    messages = chat_repo.get_messages(session_id, limit=None)
    memories = mem_repo.list_for_session(session_id)

    worldinfo = (
        wi_repo.get_by_id(chat_session.active_worldinfo_id)
        if chat_session.active_worldinfo_id
        else None
    )
    current_location = (
        wi_repo.get_location(chat_session.current_location_id)
        if chat_session.active_worldinfo_id and chat_session.current_location_id
        else None
    )
    worldinfo_locations = (
        wi_repo.list_locations(worldinfo.id)
        if worldinfo and worldinfo.id is not None
        else []
    )
    all_worldinfos = wi_repo.list_all()

    last_char_msg = next((m for m in reversed(messages) if m.role.value == "character"), None)
    last_emotion = (
        Emotion.resolve(last_char_msg.emotion_tag)
        if last_char_msg and last_char_msg.emotion_tag
        else Emotion.NEUTRAL
    )
    active_sprite = char_service.select_sprite_for_emotion(character, last_emotion)

    unlocked_gallery = char_service.get_unlocked_images(
        character, chat_session.relationship_value
    )
    session_media_images = [
        m.image_path for m in messages if m.image_path
    ]

    return render_template(
        "chat/session.html",
        chat_session=chat_session,
        character=character,
        persona=persona,
        user_personas=user_personas,
        all_sessions=all_sessions,
        messages=messages,
        memories=memories,
        worldinfo=worldinfo,
        current_location=current_location,
        worldinfo_locations=worldinfo_locations,
        all_worldinfos=all_worldinfos,
        active_sprite=active_sprite,
        unlocked_gallery=unlocked_gallery,
        session_media_images=session_media_images,
    )


@chat_bp.route("/session/<int:session_id>/update-settings", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def update_session_settings(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    chat_service = ChatService()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or chat_session.user_id != user.id:
        flash("Session nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    action = request.form.get("action", "")
    try:
        if action == "change_persona":
            new_persona_id = int(request.form.get("persona_id", 0))
            chat_service.change_persona(chat_session, new_persona_id)
            flash("Persona für diese Session aktualisiert.", "success")
        elif action == "switch_worldinfo":
            raw_wi = request.form.get("worldinfo_id", "").strip()
            new_wi_id = int(raw_wi) if raw_wi and raw_wi != "none" else None
            char = char_repo.get_by_id(chat_session.character_id)
            init_loc = char.initial_location_id if char and new_wi_id else None
            chat_service.switch_worldinfo(chat_session, new_wi_id, init_loc)
            flash("WorldInfo für diesen Chat gewechselt.", "success")
        elif action == "toggle_events":
            chat_session.events_enabled = bool(request.form.get("events_enabled"))
            flash("Event-Einstellung gespeichert.", "success")
        elif action == "rename_title":
            new_title = request.form.get("title", "").strip()
            if new_title:
                chat_session.title = new_title
                flash("Chat-Titel aktualisiert.", "success")

        chat_repo.update_session(chat_session)
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_session(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or chat_session.user_id != user.id:
        return redirect(url_for("overview.index"))

    char_id = chat_session.character_id
    chat_repo.delete_session(session_id)
    flash("Chat-Session gelöscht.", "success")
    return redirect(url_for("chat.open_character_chat", character_id=char_id))


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def edit_memory(session_id: int, memory_id: int):
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
            flash("Erinnerung aktualisiert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("chat.view_session", session_id=session_id))


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def delete_memory(session_id: int, memory_id: int):
    mem_repo = MemoryRepository()
    mem = mem_repo.get_by_id(memory_id)
    if mem is not None and mem.chat_session_id == session_id:
        mem_repo.delete_memory(memory_id)
        flash("Erinnerung gelöscht.", "success")
    return redirect(url_for("chat.view_session", session_id=session_id))
