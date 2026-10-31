from flask import Blueprint, flash, redirect, request, url_for

from application.auth.decorators import get_current_user, require_permission
from domain.permissions.models import FunctionPermission
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

personas_bp = Blueprint("personas", __name__, url_prefix="/personas")


@personas_bp.route("/create", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def create_persona():
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = PersonaRepository()
    trans_repo = TranslationRepository()
    service = PersonaService()
    storage = FileStorage()

    try:
        portrait_file = request.files.get("portrait")
        preuploaded = request.form.get("preuploaded_portrait_path", "").strip()
        if portrait_file and portrait_file.filename:
            portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
        elif preuploaded:
            portrait_path = preuploaded
        else:
            portrait_path = "portraits/default_persona.png"

        existing = repo.list_for_user(user.id)
        is_default = bool(request.form.get("is_default")) or len(existing) == 0

        persona = service.create_persona(
            user_id=user.id,
            name=request.form.get("name", ""),
            gender=request.form.get("gender", Gender.NON_BINARY.value),
            portrait_path=portrait_path,
            description=request.form.get("description", ""),
            appearance=request.form.get("appearance", ""),
            is_default=is_default,
        )

        saved = repo.create(persona)
        if saved.id is not None:
            trans_repo.save_field_variants_json(
                "persona", saved.id, "description", request.form.get("i18n_description")
            )
            trans_repo.save_field_variants_json(
                "persona", saved.id, "appearance", request.form.get("i18n_appearance")
            )
        flash(f"Persona '{persona.name}' erfolgreich erstellt.", "success")
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(request.referrer or url_for("overview.index"))


@personas_bp.route("/<int:persona_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def edit_persona(persona_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = PersonaRepository()
    trans_repo = TranslationRepository()
    service = PersonaService()
    storage = FileStorage()

    persona = repo.get_by_id(persona_id)
    if persona is None or persona.user_id != user.id:
        flash("Persona nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    try:
        portrait_path = persona.portrait_path
        portrait_file = request.files.get("portrait")
        preuploaded = request.form.get("preuploaded_portrait_path", "").strip()
        if portrait_file and portrait_file.filename:
            portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
        elif preuploaded:
            portrait_path = preuploaded

        service.update_persona(
            persona=persona,
            name=request.form.get("name", persona.name),
            gender=request.form.get("gender", persona.gender.value),
            portrait_path=portrait_path,
            description=request.form.get("description", persona.description),
            appearance=request.form.get("appearance", persona.appearance),
        )

        if request.form.get("is_default"):
            persona.is_default = True
        repo.update(persona)
        trans_repo.save_field_variants_json(
            "persona", persona_id, "description", request.form.get("i18n_description")
        )
        trans_repo.save_field_variants_json(
            "persona", persona_id, "appearance", request.form.get("i18n_appearance")
        )
        flash(f"Persona '{persona.name}' aktualisiert.", "success")
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(request.referrer or url_for("overview.index"))


@personas_bp.route("/<int:persona_id>/default", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def set_default(persona_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = PersonaRepository()
    persona = repo.get_by_id(persona_id)
    if persona and persona.user_id == user.id:
        repo.set_default(user.id, persona_id)
        flash(f"'{persona.name}' ist nun deine Standard-Persona.", "success")
    return redirect(request.referrer or url_for("overview.index"))


@personas_bp.route("/<int:persona_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def delete_persona(persona_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = PersonaRepository()
    service = PersonaService()

    persona = repo.get_by_id(persona_id)
    if persona is None or persona.user_id != user.id:
        flash("Persona nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    try:
        in_use = repo.is_used_in_any_session(persona_id)
        service.delete_persona(persona, has_active_chats=in_use)
        repo.delete(persona_id)
        flash(f"Persona '{persona.name}' gelöscht.", "success")
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(request.referrer or url_for("overview.index"))
