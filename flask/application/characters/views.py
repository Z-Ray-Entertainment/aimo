from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_permission
from application.character_helpers import save_and_persist_sprite
from application.characters.forms import CharacterForm
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.relationship_repository import RelationshipRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

characters_bp = Blueprint("characters", __name__, url_prefix="/characters")

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
    all_locations = []
    locations_by_world = {}
    target_char_id = character.id if character and character.id else None
    for wi in worldinfos:
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

    sprites_by_emotion: dict[str, list] = {em: [] for em in STANDARD_28_EMOTIONS}
    if character is not None:
        for sp in character.sprites:
            sprites_by_emotion.setdefault(sp.emotion.value, []).append(sp)

    valid_tabs = ("info", "gallery", "sprites", "dialogue", "world", "lorebooks", "collab")
    active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
    if active_tab not in valid_tabs:
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

    return render_template(
        "characters/creator.html",
        character=character,
        form=form or CharacterForm(),
        is_author=is_author,
        is_editable=is_editable,
        lorebooks=lorebooks,
        worldinfos=worldinfos,
        all_locations=all_locations,
        locations_by_world=locations_by_world,
        emotions=STANDARD_28_EMOTIONS,
        sprites_by_emotion=sprites_by_emotion,
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
            saved = char_repo.save(character)
            flash(f"Charakter '{saved.name}' erfolgreich angelegt!", "success")
            active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
            if active_tab not in ("info", "gallery", "sprites", "dialogue", "world", "lorebooks", "collab"):
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
        flash("Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    if not character.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash("Zugriff verweigert: Du kannst nur deine eigenen Charaktere oder für dich freigegebene Kreationen bearbeiten.", "error")
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
            flash(f"Charakter '{character.name}' gespeichert.", "success")
            active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
            if active_tab not in ("info", "gallery", "sprites", "dialogue", "world", "lorebooks", "collab"):
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
        flash("Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index", tab="characters"))

    copied = char_repo.duplicate(character_id, user.id)
    flash(f"Kopie '{copied.name}' als Entwurf erstellt.", "success")
    return redirect(url_for("characters.edit_character", character_id=copied.id))


@characters_bp.route("/<int:character_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_DELETE)
def delete_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    char = char_repo.get_by_id(character_id)
    if char is None or not char.is_deletable_by_user(user.id, is_admin()):
        flash("Charakter nicht gefunden oder keine Berechtigung zum Löschen.", "error")
        return redirect(url_for("overview.index", tab="characters"))

    char_repo.delete(character_id)
    flash("Charakter gelöscht.", "success")
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
        flash("Charakter nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    img_file = request.files.get("gallery_image")
    threshold = int(request.form.get("unlock_threshold", 0))
    if img_file and img_file.filename:
        try:
            saved_path = storage.save_portrait(img_file.stream, img_file.filename)
            img_entity = char_service.add_gallery_image(character, saved_path, threshold)
            char_repo.add_gallery_image(character_id, img_entity)
            flash("9:16-Galeriebild hinzugefügt.", "success")
        except AimoError as exc:
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
        flash("Charakter nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    char_repo.delete_gallery_image(image_id)
    flash("Galeriebild entfernt.", "success")
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
        flash("Charakter nicht gefunden oder keine Berechtigung.", "error")
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
            flash(f"Sprite '{emotion.value}_{persisted.variant}' hochgeladen.", "success")
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
        flash("Charakter nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    char_repo.delete_sprite(character_id, emotion, variant)
    flash(f"Sprite {emotion}_{variant} gelöscht.", "success")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))
