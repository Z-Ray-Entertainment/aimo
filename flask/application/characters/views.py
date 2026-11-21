from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_permission
from application.character_helpers import save_and_persist_sprite
from application.characters.forms import CharacterForm
from application.ui_helpers import tr
from application.worldinfo.forms import EventForm
from i18n import gettext_noop as _
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.permissions.models import FunctionPermission
from domain.worldinfo.services import WorldInfoService
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

characters_bp = Blueprint("characters", __name__, url_prefix="/characters")

_VALID_CHARACTER_TABS = ("info", "gallery", "sprites", "dialogue", "world", "events", "lorebooks", "collab")

STANDARD_28_EMOTIONS: list[str] = [
    Emotion.ADMIRE.value,
    Emotion.AMUSED.value,
    Emotion.ANGER.value,
    Emotion.ANNOYED.value,
    Emotion.APPROVAL.value,
    Emotion.CARING.value,
    Emotion.CONFUSED.value,
    Emotion.CURIOUS.value,
    Emotion.DESIRE.value,
    Emotion.DISAPPOINTED.value,
    Emotion.DISAPPROVAL.value,
    Emotion.DISGUST.value,
    Emotion.EMBARRASSED.value,
    Emotion.EXCITED.value,
    Emotion.FEAR.value,
    Emotion.GRATITUDE.value,
    Emotion.GRIEF.value,
    Emotion.JOY.value,
    Emotion.LOVE.value,
    Emotion.NERVOUSNESS.value,
    Emotion.NEUTRAL.value,
    Emotion.OPTIMISTIC.value,
    Emotion.PRIDE.value,
    Emotion.REALIZE.value,
    Emotion.RELIEF.value,
    Emotion.REMORSE.value,
    Emotion.SAD.value,
    Emotion.SURPRISE.value,
]


def _render_creator(character=None, form=None):
    user = get_current_user()
    uid = user.id if user and user.id else None
    lb_repo = LorebookRepository()
    wi_repo = WorldInfoRepository()
    lorebooks = lb_repo.list_for_user(uid)
    worldinfos = wi_repo.list_all(uid)
    world_map = {wi.id: wi for wi in worldinfos if wi.id is not None}
    suggested_wi_id = (
        character.suggested_worldinfo_id
        if character
        else (form.suggested_worldinfo_id if form else None)
    )
    ordered_worldinfos = sorted(
        worldinfos,
        key=lambda w: (0 if suggested_wi_id and w.id == suggested_wi_id else 1, w.name.lower()),
    )
    all_locations = []
    locations_by_world = {}
    target_char_id = character.id if character and character.id else None
    for wi in ordered_worldinfos:
        if wi.id is not None:
            raw_locs = wi_repo.list_locations(wi.id)
            locs = [
                loc for loc in raw_locs
                if loc.character_id is None or loc.character_id == target_char_id
            ]
            locations_by_world[wi.id] = [
                {"id": loc.id, "name": loc.name, "worldinfo_id": loc.worldinfo_id}
                for loc in locs
            ]
            all_locations.extend(locs)

    event_locations = []
    if character and character.suggested_worldinfo_id:
        suggested_wi = (
            world_map.get(character.suggested_worldinfo_id)
            or wi_repo.get_by_id(character.suggested_worldinfo_id)
        )
        if suggested_wi and suggested_wi.id is not None and suggested_wi.is_visible_to_user(uid or 0, is_admin()):
            raw_ev_locs = wi_repo.list_locations(suggested_wi.id)
            event_locations = [
                loc for loc in raw_ev_locs
                if loc.character_id is None or loc.character_id == target_char_id
            ]

    loc_map = {loc.id: loc for loc in event_locations if loc.id is not None}
    character_events = (
        wi_repo.list_character_events(character.id)
        if character and character.id is not None
        else []
    )

    trans_repo = TranslationRepository()
    event_translations = {
        ev.id: (
            trans_repo.get_entity_translations_map("worldinfo_event", ev.id)
            or trans_repo.get_entity_translations_map("event", ev.id)
        )
        for ev in character_events
        if ev.id is not None
    }

    raw_sprites: dict[str, list] = {}
    if character is not None:
        for sp in character.sprites:
            raw_sprites.setdefault(sp.emotion.value, []).append(sp)

    ordered_emotions = ["neutral"] + [em for em in STANDARD_28_EMOTIONS if em != "neutral"]
    sprite_by_emotion = {
        em: raw_sprites[em][0]
        for em in ordered_emotions
        if em in raw_sprites and raw_sprites[em]
    }
    available_emotions = [em for em in ordered_emotions if em not in sprite_by_emotion]

    active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
    if active_tab not in _VALID_CHARACTER_TABS:
        active_tab = "info"

    is_author = (character.user_id == user.id or is_admin()) if (character and user) else True
    is_editable = (
        character.is_editable_by_user(user.id, is_admin(), user.creator_tag)
        if (character and user)
        else True
    )

    rel_repo = RelationshipRepository()
    sys_lang = user.language if user and user.language else "en"
    rel_tiers = rel_repo.list_tiers(sys_lang)
    gallery_threshold_names = {t.level: t.name for t in rel_tiers}

    char_translations = (
        trans_repo.get_entity_translations_map("character", character.id)
        if character and character.id is not None
        else {}
    )
    loc_display = {
        loc.id: {
            "name": (
                loc.name
                if getattr(loc, "is_proper_noun", False)
                else trans_repo.get_localized_field("worldinfo_location", loc.id, "name", sys_lang, loc.name)
            ),
        }
        for loc in event_locations
        if loc.id is not None
    }
    ev_display = {
        ev.id: {
            "title": (
                ev.title
                if getattr(ev, "is_proper_noun", False)
                else trans_repo.get_localized_field("worldinfo_event", ev.id, "title", sys_lang, ev.title)
            ),
            "description": trans_repo.get_localized_field(
                "worldinfo_event", ev.id, "description", sys_lang, ev.description
            ),
        }
        for ev in character_events
        if ev.id is not None
    }

    return render_template(
        "characters/creator.html",
        character=character,
        form=form or CharacterForm(),
        is_author=is_author,
        is_editable=is_editable,
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
        ev_translations=event_translations,
        event_translations=event_translations,
        char_translations=char_translations,
        emotions=STANDARD_28_EMOTIONS,
        sprite_by_emotion=sprite_by_emotion,
        available_emotions=available_emotions,
        relationship_tiers=rel_tiers,
        gallery_threshold_names=gallery_threshold_names,
        active_tab=active_tab,
    )


@characters_bp.route("/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def new_character():
    user = get_current_user()
    assert user is not None and user.id is not None
    form = CharacterForm.from_request(request.form) if request.method == "POST" else CharacterForm()

    if request.method == "POST":
        char_service = CharacterService()
        char_repo = CharacterRepository()
        storage = FileStorage()
        try:
            portrait_file = request.files.get("primary_portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
            else:
                raise AimoError("Primary Portrait ist ein Pflichtfeld beim Erstellen eines Charakters.")

            avatar_file = request.files.get("avatar_portrait")
            avatar_path = None
            if avatar_file and avatar_file.filename:
                avatar_path = storage.save_portrait(avatar_file.stream, avatar_file.filename)

            card_file = request.files.get("card_portrait")
            card_image_path = None
            if card_file and card_file.filename:
                card_image_path = storage.save_portrait(card_file.stream, card_file.filename)

            character = char_service.create_character(
                user_id=user.id,
                name=form.name,
                gender=form.gender,
                primary_portrait_path=portrait_path,
                avatar_path=avatar_path,
                card_image_path=card_image_path,
                appearance=form.appearance,
                description=form.description,
                first_message=form.first_message,
                visibility=form.visibility,
                dialogue_examples=form.dialogue_examples,
                linked_lorebook_ids=form.linked_lorebook_ids,
                lorebook_world_conditions=form.lorebook_world_conditions,
                suggested_worldinfo_id=form.suggested_worldinfo_id,
                initial_location_id=form.initial_location_id,
                initial_relationship=form.initial_relationship,
                preferred_location_ids=form.preferred_location_ids,
                disliked_location_ids=form.disliked_location_ids,
                collaborator_creator_tags=form.collaborator_creator_tags,
            )
            character.origin_language = (user.language or "en")[:2].lower()
            saved = char_repo.save(character)
            if saved.id is not None:
                from application.ui_helpers import notify_author_translation_hint

                trans_repo = TranslationRepository()
                trans_repo.save_field_variants_json("character", saved.id, "description", request.form.get("i18n_description"))
                trans_repo.save_field_variants_json("character", saved.id, "appearance", request.form.get("i18n_appearance"))
                trans_repo.save_field_variants_json("character", saved.id, "first_message", request.form.get("i18n_first_message"))
                notify_author_translation_hint("character", saved.id, "description")
            flash(tr(_("Character '%(name)s' created successfully!"), name=saved.name), "success")
            active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
            if active_tab not in _VALID_CHARACTER_TABS:
                active_tab = "info"
            return redirect(url_for("characters.edit_character", character_id=saved.id, tab=active_tab))
        except AimoError as exc:
            flash(str(exc), "error")

    return _render_creator(character=None, form=form)


@characters_bp.route("/<int:character_id>", methods=["GET"])
@characters_bp.route("/<int:character_id>/edit", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def edit_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None

    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_visible_to_user(user.id, is_admin()):
        flash(tr(_("Character not found.")), "error")
        return redirect(url_for("overview.index"))

    if not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Access denied: You can only edit your own characters or creations shared with you.")), "error")
        return redirect(url_for("overview.index"))

    is_author = (character.user_id == user.id or is_admin())

    if request.method == "POST":
        form = CharacterForm.from_request(request.form)
        try:
            portrait_path = character.primary_portrait_path
            portrait_file = request.files.get("primary_portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)

            avatar_path = character.avatar_path
            avatar_file = request.files.get("avatar_portrait")
            if avatar_file and avatar_file.filename:
                avatar_path = storage.save_portrait(avatar_file.stream, avatar_file.filename)

            card_image_path = character.card_image_path
            card_file = request.files.get("card_portrait")
            if card_file and card_file.filename:
                card_image_path = storage.save_portrait(card_file.stream, card_file.filename)

            collaborator_tags = form.collaborator_creator_tags if is_author else character.collaborator_creator_tags

            char_service.update_character(
                character=character,
                name=form.name,
                gender=form.gender,
                primary_portrait_path=portrait_path,
                avatar_path=avatar_path,
                card_image_path=card_image_path,
                appearance=form.appearance,
                description=form.description,
                first_message=form.first_message,
                visibility=form.visibility,
                dialogue_examples=form.dialogue_examples,
                linked_lorebook_ids=form.linked_lorebook_ids,
                lorebook_world_conditions=form.lorebook_world_conditions,
                suggested_worldinfo_id=form.suggested_worldinfo_id,
                initial_location_id=form.initial_location_id,
                initial_relationship=form.initial_relationship,
                preferred_location_ids=form.preferred_location_ids,
                disliked_location_ids=form.disliked_location_ids,
                collaborator_creator_tags=collaborator_tags,
            )
            character = char_repo.save(character)
            if character.id is not None:
                from application.ui_helpers import notify_author_translation_hint

                WorldInfoRepository().clear_character_event_locations_outside_world(
                    character.id, character.suggested_worldinfo_id
                )
                trans_repo = TranslationRepository()
                trans_repo.save_field_variants_json("character", character.id, "description", request.form.get("i18n_description"))
                trans_repo.save_field_variants_json("character", character.id, "appearance", request.form.get("i18n_appearance"))
                trans_repo.save_field_variants_json("character", character.id, "first_message", request.form.get("i18n_first_message"))
                notify_author_translation_hint("character", character.id, "description")
            flash(tr(_("Character '%(name)s' saved."), name=character.name), "success")
            active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
            if active_tab not in _VALID_CHARACTER_TABS:
                active_tab = "info"
            return redirect(url_for("characters.edit_character", character_id=character.id, tab=active_tab))
        except AimoError as exc:
            flash(str(exc), "error")
    else:
        form = CharacterForm(
            name=character.name,
            gender=character.gender.value,
            visibility=character.visibility,
            appearance=getattr(character, "appearance", "") or "",
            description=character.description,
            dialogue_examples=character.dialogue_examples,
            dialogue_examples_text="\n".join([
                ex["response"] if isinstance(ex, dict) else str(ex)
                for ex in character.dialogue_examples
            ]),
            first_message=character.first_message,
            suggested_worldinfo_id=character.suggested_worldinfo_id,
            initial_location_id=character.initial_location_id,
            initial_relationship=character.initial_relationship,
            linked_lorebook_ids=character.linked_lorebook_ids,
            lorebook_world_conditions=getattr(character, "lorebook_world_conditions", {}) or {},
            preferred_location_ids=character.preferred_location_ids,
            disliked_location_ids=character.disliked_location_ids,
            collaborator_creator_tags=character.collaborator_creator_tags,
            collaborator_creator_tags_text=", ".join(character.collaborator_creator_tags),
        )

    return _render_creator(character=character, form=form)


@characters_bp.route("/<int:character_id>/copy", methods=["POST"])
@characters_bp.route("/<int:character_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def copy_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    orig = char_repo.get_by_id(character_id)
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        flash(tr(_("Character not found.")), "error")
        return redirect(url_for("overview.index", tab="characters"))

    copied = char_repo.duplicate(character_id, user.id)
    flash(tr(_("Copy '%(name)s' created as draft."), name=copied.name), "success")
    return redirect(url_for("characters.edit_character", character_id=copied.id))


@characters_bp.route("/<int:character_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_DELETE)
def delete_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_deletable_by_user(user.id, is_admin()):
        flash(tr(_("Character not found or no permission to delete.")), "error")
        return redirect(url_for("overview.index", tab="characters"))

    char_repo.delete(character_id)
    flash(tr(_("Character deleted.")), "success")
    return redirect(url_for("overview.index", tab="characters"))


@characters_bp.route("/<int:character_id>/gallery/add", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_gallery_image(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    img_file = request.files.get("gallery_image")
    threshold = int(request.form.get("unlock_threshold", 0))
    if img_file and img_file.filename:
        try:
            saved_path = storage.save_portrait(img_file.stream, img_file.filename)
            img_entity = char_service.add_gallery_image(character, saved_path, threshold)
            char_repo.add_gallery_image(character_id, img_entity)
            flash(tr(_("9:16 gallery image added.")), "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))


@characters_bp.route("/<int:character_id>/gallery/<int:image_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def edit_gallery_image(character_id: int, image_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char_service = CharacterService()

    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    if not any(img.id == image_id for img in character.gallery_images):
        flash(tr(_("Gallery image not found.")), "error")
        return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))

    try:
        threshold = int(request.form.get("unlock_threshold", 0))
        validated_threshold = char_service.validate_gallery_threshold(threshold)
        char_repo.update_gallery_image_threshold(image_id, validated_threshold)
        flash(tr(_("Gallery image updated.")), "success")
    except (ValueError, AimoError) as exc:
        flash(str(exc), "error")

    return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))


@characters_bp.route("/<int:character_id>/gallery/<int:image_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_gallery_image(character_id: int, image_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    if not any(img.id == image_id for img in char.gallery_images):
        flash(tr(_("Gallery image not found.")), "error")
        return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))

    char_repo.delete_gallery_image(image_id)
    flash(tr(_("Gallery image removed.")), "success")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="gallery"))


@characters_bp.route("/<int:character_id>/sprites/upload", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    emotion = Emotion.resolve(request.form.get("emotion", "neutral"))
    sprite_file = request.files.get("sprite_file")
    if sprite_file and sprite_file.filename:
        try:
            persisted = save_and_persist_sprite(
                character=character,
                emotion=emotion,
                file_stream=sprite_file.stream,
                filename=sprite_file.filename,
                char_service=char_service,
                char_repo=char_repo,
                storage=storage,
            )
            flash(tr(_("Sprite '%(name)s' uploaded."), name=emotion.value), "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))


@characters_bp.route("/<int:character_id>/sprites/<string:emotion>/<int:variant>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_sprite(character_id: int, emotion: str, variant: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    char_repo.delete_sprites_by_emotion(character_id, emotion)
    flash(tr(_("Sprite %(name)s deleted."), name=emotion), "success")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))


def _validate_character_event_location(
    wi_repo: WorldInfoRepository,
    location_id: int | None,
    character,
    user_id: int,
) -> bool:
    if location_id is None:
        return True
    if not character.suggested_worldinfo_id:
        return False
    loc = wi_repo.get_location(location_id)
    if loc is None or loc.worldinfo_id != character.suggested_worldinfo_id:
        return False
    wi = wi_repo.get_by_id(loc.worldinfo_id)
    if wi is None or not wi.is_visible_to_user(user_id, is_admin()):
        return False
    return loc.is_accessible_by_character(character.id)


@characters_bp.route("/<int:character_id>/events/add", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_event(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    form = EventForm.from_request(request.form)
    wi_repo = WorldInfoRepository()
    if not _validate_character_event_location(wi_repo, form.location_id, character, user.id):
        flash(tr(_("Invalid or inaccessible location selected.")), "error")
        return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))

    service = WorldInfoService()
    try:
        ev = service.add_event(
            worldinfo_id=None,
            character_id=character_id,
            title=form.title,
            description=form.description,
            probability=form.probability,
            one_shot=form.one_shot,
            location_id=form.location_id,
            min_relationship=form.min_relationship,
            max_relationship=form.max_relationship,
            is_proper_noun=form.is_proper_noun,
        )
        saved_ev = wi_repo.add_event(ev)
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
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))


@characters_bp.route("/<int:character_id>/events/<int:event_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def edit_event(character_id: int, event_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    form = EventForm.from_request(request.form)
    wi_repo = WorldInfoRepository()
    if not _validate_character_event_location(wi_repo, form.location_id, character, user.id):
        flash(tr(_("Invalid or inaccessible location selected.")), "error")
        return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))

    service = WorldInfoService()
    ev = wi_repo.get_event(event_id)
    if ev is not None and ev.character_id == character_id:
        try:
            service.update_event(
                event=ev,
                title=form.title,
                description=form.description,
                probability=form.probability,
                one_shot=form.one_shot,
                location_id=form.location_id,
                min_relationship=form.min_relationship,
                max_relationship=form.max_relationship,
                is_proper_noun=form.is_proper_noun,
            )
            wi_repo.update_event(ev)
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
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))


@characters_bp.route("/<int:character_id>/events/<int:event_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_event(character_id: int, event_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    character = char_repo.get_by_id(character_id)
    if character is None or not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Character not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    wi_repo = WorldInfoRepository()
    ev = wi_repo.get_event(event_id)
    if ev is not None and ev.character_id == character_id:
        wi_repo.delete_event(event_id)
        flash(tr(_("Event deleted.")), "success")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="events"))
