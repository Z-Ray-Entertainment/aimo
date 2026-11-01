from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_permission
from application.chat.forms import MemoryEditForm, StartChatForm
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
from infrastructure.repositories.memory_repository import MemoryRepository
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from shared.exceptions import AimoError
from shared.utils import replace_roleplay_placeholders

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


def _get_user_system_language() -> str:
    cookie_lang = request.cookies.get("aimo_sys_lang", "").strip().lower()[:2]
    if cookie_lang in ("de", "en", "fr", "es", "it", "ja"):
        return cookie_lang
    best = request.accept_languages.best_match(["de", "en", "fr", "es", "it", "ja"])
    return best if best else "de"


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

    worldinfos = wi_repo.list_all(user.id)
    trans_repo = TranslationRepository()
    sys_lang = _get_user_system_language()

    if request.method == "POST":
        form = StartChatForm.from_request(request.form)
        selected_persona_id = form.persona_id or (personas[0].id or 0)
        selected_persona = next((p for p in personas if p.id == selected_persona_id), personas[0])
        localized_welcome = trans_repo.get_localized_field(
            "character", character.id, "first_message", sys_lang, character.first_message
        )
        initial_loc = None
        if form.worldinfo_id:
            wi = wi_repo.get_by_id(form.worldinfo_id)
            if wi and wi.initial_location_id:
                initial_loc = wi.initial_location_id
        if initial_loc is None and character.initial_location_id and form.worldinfo_id:
            initial_loc = character.initial_location_id
        try:
            session_obj, first_msg = chat_service.create_session(
                user_id=user.id,
                character=character,
                persona_id=selected_persona_id,
                worldinfo_id=form.worldinfo_id,
                title=form.title or None,
                persona_name=selected_persona.name,
                localized_welcome_text=localized_welcome,
                initial_location_id=initial_loc,
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
        localized_welcome = trans_repo.get_localized_field(
            "character", character.id, "first_message", sys_lang, character.first_message
        )
        session_obj, first_msg = chat_service.create_session(
            user_id=user.id,
            character=character,
            persona_id=default_persona.id or 0,
            worldinfo_id=None,
            persona_name=default_persona.name,
            localized_welcome_text=localized_welcome,
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

    trans_repo = TranslationRepository()
    sys_lang = _get_user_system_language()
    persona_name = persona.name if persona else user.username

    for msg in messages:
        if msg.message_idx == 0 and msg.role.value == "character":
            bg_welcome = trans_repo.get_localized_field(
                "character", character.id, "first_message", sys_lang, msg.localized_content
            )
            msg.localized_content = replace_roleplay_placeholders(
                bg_welcome, character.name, persona_name
            )
        else:
            msg.localized_content = replace_roleplay_placeholders(
                msg.localized_content, character.name, persona_name
            )

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
    worldinfo_events = (
        wi_repo.list_events(worldinfo.id)
        if worldinfo and worldinfo.id is not None
        else []
    )
    all_worldinfos = wi_repo.list_all(user.id)

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

    settings = SettingsRepository().get_settings()
    comfyui_available = (
        bool(settings.comfyui_url and settings.comfyui_url.strip())
        and get_image_gen_provider(settings).check_health()
    )
    persona_trans = (
        trans_repo.get_entity_translations_map("persona", persona.id)
        if persona and persona.id
        else {}
    )

    is_admin = bool(user and (user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS)))

    return render_template(
        "chat/session.html",
        chat_session=chat_session,
        character=character,
        persona=persona,
        persona_i18n_description=persona_trans.get("description", {}),
        persona_i18n_appearance=persona_trans.get("appearance", {}),
        user_personas=user_personas,
        all_sessions=all_sessions,
        messages=messages,
        memories=memories,
        worldinfo=worldinfo,
        current_location=current_location,
        worldinfo_locations=worldinfo_locations,
        worldinfo_events=worldinfo_events,
        all_worldinfos=all_worldinfos,
        active_sprite=active_sprite,
        unlocked_gallery=unlocked_gallery,
        session_media_images=session_media_images,
        sys_lang=sys_lang,
        comfyui_available=comfyui_available,
        is_admin=is_admin,
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
            init_loc = None
            if new_wi_id:
                wi = wi_repo.get_by_id(new_wi_id)
                if wi and wi.initial_location_id:
                    init_loc = wi.initial_location_id
            if init_loc is None and new_wi_id:
                char = char_repo.get_by_id(chat_session.character_id)
                init_loc = char.initial_location_id if char else None
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


@chat_bp.route("/session/<int:session_id>/memories/<int:memory_id>/recalculate", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def recalculate_memory(session_id: int, memory_id: int):
    chat_repo = ChatRepository()
    mem_repo = MemoryRepository()
    settings_repo = SettingsRepository()
    mem_service = MemoryService()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": "Session not found."}, 404
        flash("Chat-Session nicht gefunden.", "error")
        return redirect(url_for("chat.open_character_chat", character_id=1))

    target_memory = mem_repo.get_by_id(memory_id)
    if target_memory is None or target_memory.chat_session_id != session_id:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": "Memory not found."}, 404
        flash("Erinnerung nicht gefunden.", "error")
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
        flash("Keine Nachrichten für diese Erinnerungsepisode gefunden.", "error")
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
        flash("Erinnerung erfolgreich neu berechnet.", "success")
    except Exception as exc:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return {"error": str(exc)}, 500
        flash(f"Fehler bei der Neuberechnung: {exc}", "error")

    return redirect(url_for("chat.view_session", session_id=session_id))

