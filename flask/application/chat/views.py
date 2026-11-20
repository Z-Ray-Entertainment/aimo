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
from application.chat.helpers import _build_lorebook_view_data, _get_user_system_language


@chat_bp.route("/character/<int:character_id>", methods=["GET"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def open_character_chat(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    char_repo = CharacterRepository()

    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_visible_to_user(user.id, is_admin_user()):
        flash(tr(_("Character not found.")), "error")
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
    if character is None or not character.is_visible_to_user(user.id, is_admin_user()):
        flash(tr(_("Character not found.")), "error")
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

    trans_repo = TranslationRepository()
    sys_lang = _get_user_system_language()
    admin_flag = is_admin_user()
    worldinfos = [
        wi
        for wi in wi_repo.list_all(user.id)
        if wi.is_editable_by_user(user.id, admin_flag, user.creator_tag)
        or is_worldinfo_ready_for_language(wi, sys_lang, trans_repo, wi_repo)
    ]

    if request.method == "POST":
        form = StartChatForm.from_request(request.form)
        if form.worldinfo_id:
            selected_wi = wi_repo.get_by_id(form.worldinfo_id)
            if selected_wi is None or not selected_wi.is_visible_to_user(user.id, admin_flag):
                flash(tr(_("Invalid WorldInfo.")), "error")
                return redirect(url_for("chat.new_character_chat", character_id=character_id))
            if not selected_wi.is_editable_by_user(
                user.id, admin_flag, user.creator_tag
            ) and not is_worldinfo_ready_for_language(selected_wi, sys_lang, trans_repo, wi_repo):
                flash(tr(_("This world is not yet available in your language.")), "warning")
                return redirect(url_for("chat.new_character_chat", character_id=character_id))
        selected_persona_id = form.persona_id or (personas[0].id or 0)
        selected_persona = next((p for p in personas if p.id == selected_persona_id), personas[0])
        localized_welcome = trans_repo.get_localized_field(
            "character", character.id, "first_message", sys_lang, character.first_message
        )
        initial_loc = None
        if character.initial_location_id and form.worldinfo_id:
            loc = wi_repo.get_location(character.initial_location_id)
            if loc and loc.worldinfo_id == form.worldinfo_id:
                if loc.character_id is None or loc.character_id == character.id:
                    initial_loc = character.initial_location_id
        try:
            disabled_lb_set = set(form.disabled_lorebook_ids)
            session_obj, first_msg = chat_service.create_session(
                user_id=user.id,
                character=character,
                persona_id=selected_persona_id,
                worldinfo_id=form.worldinfo_id,
                title=form.title or None,
                persona_name=selected_persona.name,
                localized_welcome_text=localized_welcome,
                initial_location_id=initial_loc,
                disabled_lorebook_ids=disabled_lb_set,
                custom_lorebook_ids=form.custom_lorebook_ids,
                thinking_enabled=form.thinking_enabled,
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

    initial_wi = None
    if character.suggested_worldinfo_id:
        initial_wi = next((wi for wi in worldinfos if wi.id == character.suggested_worldinfo_id), None)

    is_admin = bool(user and (user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS)))
    lorebook_data = _build_lorebook_view_data(user.id, character, worldinfo=initial_wi, is_admin=is_admin)

    lb_repo = LorebookRepository()
    all_visible = lb_repo.list_visible(user.id)
    all_map = {lb.id: lb for lb in all_visible if lb.id is not None}
    worldinfo_lorebooks_map = {}
    worldinfo_names_map = {str(wi.id): wi.name for wi in worldinfos if wi.id is not None}
    for wi in worldinfos:
        if wi.id and wi.lorebook_id:
            lb = all_map.get(wi.lorebook_id) or lb_repo.get_by_id(wi.lorebook_id)
            if lb:
                entries = lb_repo.list_entries(lb.id, user_id=user.id, is_admin=is_admin) if lb.id else []
                all_tags = sorted({t for e in entries for t in e.tags})
                worldinfo_lorebooks_map[str(wi.id)] = {
                    "id": lb.id,
                    "name": lb.name,
                    "description": lb.description,
                    "tags": all_tags,
                    "entry_count": len(entries),
                    "source": "Welt",
                }

    character_lorebook_world_conditions = getattr(character, "lorebook_world_conditions", {}) or {}

    return render_template(
        "chat/select_worldinfo.html",
        character=character,
        personas=personas,
        default_persona=default_persona,
        worldinfos=worldinfos,
        lorebook_data=lorebook_data,
        worldinfo_lorebooks_map=worldinfo_lorebooks_map,
        worldinfo_names_map=worldinfo_names_map,
        character_lorebook_world_conditions=character_lorebook_world_conditions,
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
        flash(tr(_("Chat session not found.")), "error")
        return redirect(url_for("overview.index"))

    chat_service.apply_time_decay(chat_session)
    chat_repo.update_session(chat_session)

    character = char_repo.get_by_id(chat_session.character_id)
    if character is None or not character.is_visible_to_user(user.id, is_admin_user()):
        flash(tr(_("Associated character not found.")), "error")
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
    initial_location = (
        wi_repo.get_location(chat_session.initial_location_id)
        if chat_session.active_worldinfo_id and chat_session.initial_location_id
        else current_location
    )
    raw_locations = (
        wi_repo.list_locations(worldinfo.id)
        if worldinfo and worldinfo.id is not None
        else []
    )
    worldinfo_locations = [
        loc for loc in raw_locations
        if loc.character_id is None or loc.character_id == character.id
    ]
    for loc_obj in [current_location, initial_location, *worldinfo_locations]:
        if loc_obj is not None and loc_obj.id is not None:
            loc_obj.name = trans_repo.get_localized_field(
                "worldinfo_location", loc_obj.id, "name", sys_lang, loc_obj.name
            )
            loc_obj.description = trans_repo.get_localized_field(
                "worldinfo_location", loc_obj.id, "description", sys_lang, loc_obj.description
            )
    worldinfo_events = (
        wi_repo.list_events(worldinfo.id)
        if worldinfo and worldinfo.id is not None
        else []
    )
    character_events = (
        wi_repo.list_character_events(character.id)
        if character and character.id is not None
        else []
    )
    is_admin = bool(user and (user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS)))
    all_worldinfos = [
        wi
        for wi in wi_repo.list_all(user.id)
        if wi.is_editable_by_user(user.id, is_admin, user.creator_tag)
        or is_worldinfo_ready_for_language(wi, sys_lang, trans_repo, wi_repo)
    ]

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
    img_gen = get_image_gen_provider(settings)
    image_gen_available = type(img_gen).is_enabled() and img_gen.check_health()
    persona_trans = (
        trans_repo.get_entity_translations_map("persona", persona.id)
        if persona and persona.id
        else {}
    )

    is_admin = bool(user and (user.is_initial_admin or has_perm(FunctionPermission.ADMIN_ACCESS)))
    can_debug_relationship = (
        is_admin
        or bool(character and character.is_editable_by_user(user.id, is_admin, user.creator_tag))
    )
    can_view_event_counter = (
        can_debug_relationship
        or bool(worldinfo and worldinfo.is_editable_by_user(user.id, is_admin, user.creator_tag))
    )

    lorebook_data = _build_lorebook_view_data(
        user.id, character, worldinfo=worldinfo, chat_session=chat_session, is_admin=is_admin
    )

    rel_repo = RelationshipRepository()
    rel_tier = rel_repo.get_tier(chat_session.relationship_value, language=sys_lang)
    gallery_threshold_names = {
        lvl: rel_repo.get_tier(lvl, language=sys_lang).name
        for lvl in range(-100, 101, 10)
    }

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
        lorebook_data=lorebook_data,
        worldinfo=worldinfo,
        current_location=current_location,
        initial_location=initial_location,
        worldinfo_locations=worldinfo_locations,
        worldinfo_events=worldinfo_events,
        character_events=character_events,
        all_worldinfos=all_worldinfos,
        active_sprite=active_sprite,
        unlocked_gallery=unlocked_gallery,
        session_media_images=session_media_images,
        sys_lang=sys_lang,
        relationship_tier_name=rel_tier.name,
        gallery_threshold_names=gallery_threshold_names,
        image_gen_available=image_gen_available,
        comfyui_available=image_gen_available,
        is_admin=is_admin,
        can_view_event_counter=can_view_event_counter,
        can_debug_relationship=can_debug_relationship,
    )


@chat_bp.route("/session/<int:session_id>/update-settings", methods=["POST"])
@require_permission(FunctionPermission.CHAT_ACCESS)
def update_session_settings(session_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    chat_repo = ChatRepository()
    char_repo = CharacterRepository()
    persona_repo = PersonaRepository()
    wi_repo = WorldInfoRepository()
    chat_service = ChatService()

    chat_session = chat_repo.get_session(session_id)
    if chat_session is None or chat_session.user_id != user.id:
        flash(tr(_("Session not found.")), "error")
        return redirect(url_for("overview.index"))

    action = request.form.get("action", "")
    try:
        if action == "change_persona":
            new_persona_id = int(request.form.get("persona_id", 0))
            new_persona = persona_repo.get_by_id(new_persona_id)
            if new_persona is None or (new_persona.user_id != user.id and not user.is_initial_admin):
                flash(tr(_("Invalid persona.")), "error")
                return redirect(url_for("chat.view_session", session_id=session_id))
            chat_service.change_persona(chat_session, new_persona_id)
            flash(tr(_("Persona updated for this session.")), "success")
        elif action == "switch_worldinfo":
            raw_wi = request.form.get("worldinfo_id", "").strip()
            new_wi_id = int(raw_wi) if raw_wi and raw_wi != "none" else None
            init_loc = None
            if new_wi_id:
                wi = wi_repo.get_by_id(new_wi_id)
                if wi is None or not wi.is_visible_to_user(user.id, is_admin_user()):
                    flash(tr(_("Invalid WorldInfo.")), "error")
                    return redirect(url_for("chat.view_session", session_id=session_id))
                if not wi.is_editable_by_user(
                    user.id, is_admin_user(), user.creator_tag
                ) and not is_worldinfo_ready_for_language(
                    wi, _get_user_system_language(), TranslationRepository(), wi_repo
                ):
                    flash(tr(_("This world is not yet available in your language.")), "warning")
                    return redirect(url_for("chat.view_session", session_id=session_id))
                char = char_repo.get_by_id(chat_session.character_id)
                if char and char.initial_location_id:
                    loc = wi_repo.get_location(char.initial_location_id)
                    if loc and loc.worldinfo_id == new_wi_id:
                        if loc.character_id is None or loc.character_id == char.id:
                            init_loc = char.initial_location_id
            chat_service.switch_worldinfo(chat_session, new_wi_id, init_loc)
            flash(tr(_("WorldInfo changed for this chat.")), "success")
        elif action == "toggle_events":
            chat_session.events_enabled = bool(request.form.get("events_enabled"))
            flash(tr(_("Event setting saved.")), "success")
        elif action == "toggle_thinking":
            raw_val = request.form.get("thinking_enabled")
            if raw_val is not None:
                chat_session.thinking_enabled = str(raw_val).strip() in ("1", "true", "True", "on")
            else:
                chat_session.thinking_enabled = not chat_session.thinking_enabled
            if chat_session.thinking_enabled:
                flash(tr(_("Thinking enabled.")), "success")
            else:
                flash(tr(_("Thinking disabled.")), "success")
        elif action == "rename_title":
            new_title = request.form.get("title", "").strip()
            if new_title:
                chat_session.title = new_title
                flash(tr(_("Chat title updated.")), "success")

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
        return redirect(url_for("overview.index", tab="characters"))

    char_id = chat_session.character_id
    chat_repo.delete_session(session_id)
    flash(tr(_("Chat session deleted.")), "success")

    redirect_to = request.form.get("redirect_to") or request.args.get("redirect_to")
    current_session_id = request.form.get("current_session_id")
    if redirect_to == "session" and current_session_id:
        try:
            curr_id = int(current_session_id)
            if curr_id != session_id:
                curr_session = chat_repo.get_session(curr_id)
                if curr_session and curr_session.user_id == user.id:
                    return redirect(url_for("chat.view_session", session_id=curr_id))
        except ValueError:
            pass

    return redirect(url_for("overview.index", tab="characters"))

