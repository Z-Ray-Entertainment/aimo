from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_permission
from application.characters.forms import CharacterForm
from domain.characters.models import Emotion
from domain.characters.services import CharacterService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.character_repository import CharacterRepository
from infrastructure.repositories.lorebook_repository import LorebookRepository
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
    for wi in worldinfos:
        if wi.id is not None:
            all_locations.extend(wi_repo.list_locations(wi.id))

    sprites_by_emotion: dict[str, list] = {em: [] for em in STANDARD_28_EMOTIONS}
    if character is not None:
        for sp in character.sprites:
            sprites_by_emotion.setdefault(sp.emotion.value, []).append(sp)

    active_tab = request.args.get("tab", "info")
    if active_tab not in ("info", "sprites") or character is None:
        active_tab = "info"

    trans_repo = TranslationRepository()
    field_translations = (
        trans_repo.get_entity_translations_map("character", character.id)
        if character and character.id
        else {}
    )

    return render_template(
        "characters/creator.html",
        character=character,
        form=form or CharacterForm(),
        lorebooks=lorebooks,
        worldinfos=worldinfos,
        all_locations=all_locations,
        emotions=STANDARD_28_EMOTIONS,
        sprites_by_emotion=sprites_by_emotion,
        active_tab=active_tab,
        field_translations=field_translations,
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

            examples = [
                line.strip()
                for line in form.dialogue_examples_text.splitlines()
                if line.strip()
            ]
            character = char_service.create_character(
                user_id=user.id,
                name=form.name,
                gender=form.gender,
                primary_portrait_path=portrait_path,
                description=form.description,
                first_message=form.first_message,
                visibility=form.visibility,
                dialogue_examples=examples,
                linked_lorebook_ids=form.linked_lorebook_ids,
                suggested_worldinfo_id=form.suggested_worldinfo_id,
                initial_location_id=form.initial_location_id,
                initial_relationship=form.initial_relationship,
                preferred_location_ids=form.preferred_location_ids,
                disliked_location_ids=form.disliked_location_ids,
            )
            saved = char_repo.save(character)
            trans_repo = TranslationRepository()
            for fname in ("description", "dialogue_examples", "first_message"):
                trans_repo.save_field_variants_json(
                    "character", saved.id, fname, request.form.get(f"i18n_{fname}")
                )
            flash(f"Charakter '{saved.name}' erfolgreich angelegt!", "success")
            return redirect(url_for("characters.edit_character", character_id=saved.id))
        except AimoError as exc:
            flash(str(exc), "error")

    return _render_creator(character=None, form=form)


@characters_bp.route("/<int:character_id>", methods=["GET"])
@characters_bp.route("/<int:character_id>/edit", methods=["GET", "POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def edit_character(character_id: int):
    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None:
        flash("Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    if request.method == "POST":
        form = CharacterForm.from_request(request.form)
        try:
            portrait_path = character.primary_portrait_path
            portrait_file = request.files.get("primary_portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)

            examples = [
                line.strip()
                for line in form.dialogue_examples_text.splitlines()
                if line.strip()
            ]
            char_service.update_character(
                character=character,
                name=form.name,
                gender=form.gender,
                primary_portrait_path=portrait_path,
                description=form.description,
                first_message=form.first_message,
                visibility=form.visibility,
                dialogue_examples=examples,
                linked_lorebook_ids=form.linked_lorebook_ids,
                suggested_worldinfo_id=form.suggested_worldinfo_id,
                initial_location_id=form.initial_location_id,
                initial_relationship=form.initial_relationship,
                preferred_location_ids=form.preferred_location_ids,
                disliked_location_ids=form.disliked_location_ids,
            )
            character = char_repo.save(character)
            trans_repo = TranslationRepository()
            for fname in ("description", "dialogue_examples", "first_message"):
                trans_repo.save_field_variants_json(
                    "character", character.id, fname, request.form.get(f"i18n_{fname}")
                )
            flash(f"Charakter '{character.name}' gespeichert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")
    else:
        form = CharacterForm(
            name=character.name,
            gender=character.gender.value,
            visibility=character.visibility,
            description=character.description,
            dialogue_examples_text="\n".join(character.dialogue_examples),
            first_message=character.first_message,
            suggested_worldinfo_id=character.suggested_worldinfo_id,
            initial_location_id=character.initial_location_id,
            initial_relationship=character.initial_relationship,
            linked_lorebook_ids=character.linked_lorebook_ids,
            preferred_location_ids=character.preferred_location_ids,
            disliked_location_ids=character.disliked_location_ids,
        )

    return _render_creator(character=character, form=form)


@characters_bp.route("/<int:character_id>/copy", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_CREATE)
def copy_character(character_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    char_repo = CharacterRepository()
    orig = char_repo.get_by_id(character_id)
    if orig is None:
        flash("Charakter nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    orig.id = None
    orig.user_id = user.id
    orig.name = f"{orig.name} (Kopie)"
    orig.visibility = "private"
    copied = char_repo.save(orig)
    flash(f"Kopie '{copied.name}' als Entwurf erstellt.", "success")
    return redirect(url_for("characters.edit_character", character_id=copied.id))


@characters_bp.route("/<int:character_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_DELETE)
def delete_character(character_id: int):
    char_repo = CharacterRepository()
    char_repo.delete(character_id)
    flash("Charakter gelöscht.", "success")
    return redirect(url_for("overview.index"))


@characters_bp.route("/<int:character_id>/gallery/add", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def add_gallery_image(character_id: int):
    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None:
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

    return redirect(url_for("characters.edit_character", character_id=character_id))


@characters_bp.route("/<int:character_id>/gallery/<int:image_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_gallery_image(character_id: int, image_id: int):
    char_repo = CharacterRepository()
    char_repo.delete_gallery_image(image_id)
    flash("Galeriebild entfernt.", "success")
    return redirect(url_for("characters.edit_character", character_id=character_id))


@characters_bp.route("/<int:character_id>/sprites/upload", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def upload_sprite(character_id: int):
    char_repo = CharacterRepository()
    char_service = CharacterService()
    storage = FileStorage()

    character = char_repo.get_by_id(character_id)
    if character is None:
        return redirect(url_for("overview.index"))

    emotion = Emotion.resolve(request.form.get("emotion", "neutral"))
    sprite_file = request.files.get("sprite_file")
    if sprite_file and sprite_file.filename:
        try:
            temp_sp = char_service.add_sprite(character, emotion, "pending")
            saved_path = storage.save_sprite(
                character_id=character_id,
                content=sprite_file.stream,
                filename=sprite_file.filename,
                emotion=emotion.value,
                variant=temp_sp.variant,
            )
            temp_sp.file_path = saved_path
            char_repo.add_sprite(character_id, temp_sp)
            flash(f"Sprite '{emotion.value}_{temp_sp.variant}' hochgeladen.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))


@characters_bp.route("/<int:character_id>/sprites/<string:emotion>/<int:variant>/delete", methods=["POST"])
@require_permission(FunctionPermission.CHARACTER_EDIT)
def delete_sprite(character_id: int, emotion: str, variant: int):
    char_repo = CharacterRepository()
    char_repo.delete_sprite(character_id, emotion, variant)
    flash(f"Sprite {emotion}_{variant} gelöscht.", "success")
    return redirect(url_for("characters.edit_character", character_id=character_id, tab="sprites"))
