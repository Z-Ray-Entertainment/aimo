from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, require_auth, require_permission
from domain.permissions.models import FunctionPermission
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

api_personas_bp = Blueprint("api_personas", __name__, url_prefix="/api/personas")


@api_personas_bp.route("", methods=["GET"])
@require_auth
def list_personas():
    user = get_current_user()
    repo = PersonaRepository()
    trans_repo = TranslationRepository()
    personas = repo.list_for_user(user.id)
    return jsonify(
        {
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "gender": p.gender.value,
                    "portrait_path": p.portrait_path,
                    "description": p.description,
                    "appearance": p.appearance,
                    "is_default": p.is_default,
                    "in_use": repo.is_used_in_any_session(p.id) if p.id else False,
                    "i18n": trans_repo.get_entity_translations_map("persona", p.id) if p.id else {},
                }
                for p in personas
            ]
        }
    )


@api_personas_bp.route("", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def create_persona():
    user = get_current_user()
    repo = PersonaRepository()
    trans_repo = TranslationRepository()
    service = PersonaService()
    storage = FileStorage()

    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            portrait_path = data.get("portrait_path", "portraits/default_persona.png")
        else:
            data = request.form.to_dict()
            portrait_file = request.files.get("portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
            else:
                portrait_path = data.get("portrait_path") or data.get("preuploaded_portrait_path") or "portraits/default_persona.png"

        existing = repo.list_for_user(user.id)
        is_default = bool(data.get("is_default")) or len(existing) == 0

        origin_language = (
            str(data.get("origin_language") or user.language or "en").strip().lower()[:2] or "en"
        )
        persona = service.create_persona(
            user_id=user.id,
            name=data.get("name", ""),
            gender=data.get("gender", Gender.NON_BINARY.value),
            portrait_path=portrait_path,
            description=data.get("description", ""),
            appearance=data.get("appearance", ""),
            is_default=is_default,
            origin_language=origin_language,
        )

        saved = repo.create(persona)
        if saved.id is not None:
            i18n_desc = data.get("i18n_description")
            i18n_app = data.get("i18n_appearance")
            if isinstance(i18n_desc, str):
                trans_repo.save_field_variants_json("persona", saved.id, "description", i18n_desc)
            if isinstance(i18n_app, str):
                trans_repo.save_field_variants_json("persona", saved.id, "appearance", i18n_app)
        return jsonify(
            {
                "id": saved.id,
                "name": saved.name,
                "gender": saved.gender.value,
                "portrait_path": saved.portrait_path,
                "description": saved.description,
                "appearance": saved.appearance,
                "is_default": saved.is_default,
            }
        ), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_personas_bp.route("/<int:persona_id>", methods=["PUT", "POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def update_persona(persona_id: int):
    user = get_current_user()
    repo = PersonaRepository()
    trans_repo = TranslationRepository()
    service = PersonaService()
    storage = FileStorage()

    persona = repo.get_by_id(persona_id)
    if persona is None or persona.user_id != user.id:
        return jsonify({"error": "Persona not found."}), 404

    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            portrait_path = data.get("portrait_path", persona.portrait_path)
        else:
            data = request.form.to_dict()
            portrait_file = request.files.get("portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)
            else:
                portrait_path = data.get("portrait_path") or data.get("preuploaded_portrait_path") or persona.portrait_path

        service.update_persona(
            persona=persona,
            name=data.get("name", persona.name),
            gender=data.get("gender", persona.gender.value),
            portrait_path=portrait_path,
            description=data.get("description", persona.description),
            appearance=data.get("appearance", persona.appearance),
        )
        if data.get("is_default"):
            persona.is_default = True

        saved = repo.update(persona)
        i18n_desc = data.get("i18n_description")
        i18n_app = data.get("i18n_appearance")
        if isinstance(i18n_desc, str):
            trans_repo.save_field_variants_json("persona", persona_id, "description", i18n_desc)
        if isinstance(i18n_app, str):
            trans_repo.save_field_variants_json("persona", persona_id, "appearance", i18n_app)
        return jsonify(
            {
                "id": saved.id,
                "name": saved.name,
                "gender": saved.gender.value,
                "portrait_path": saved.portrait_path,
                "description": saved.description,
                "appearance": saved.appearance,
                "is_default": saved.is_default,
            }
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_personas_bp.route("/analyze-portrait", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def analyze_uploaded_or_existing_portrait():
    user = get_current_user()
    repo = PersonaRepository()
    service = PersonaService()
    storage = FileStorage()

    portrait_path: str = ""
    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            raw_pid = data.get("persona_id")
            raw_path = str(data.get("portrait_path", "")).strip()
        else:
            data = request.form.to_dict()
            raw_pid = data.get("persona_id")
            raw_path = str(data.get("portrait_path") or data.get("preuploaded_portrait_path") or "").strip()
            portrait_file = request.files.get("portrait")
            if portrait_file and portrait_file.filename:
                portrait_path = storage.save_portrait(portrait_file.stream, portrait_file.filename)

        if not portrait_path and raw_pid and str(raw_pid).isdigit():
            persona = repo.get_by_id(int(raw_pid))
            if persona is None or persona.user_id != user.id:
                return jsonify({"error": "Persona nicht gefunden."}), 404
            portrait_path = persona.portrait_path
        elif not portrait_path and raw_path:
            owned_paths = {p.portrait_path for p in repo.list_for_user(user.id) if p.portrait_path}
            if raw_path not in owned_paths:
                return jsonify({"error": "Persona nicht gefunden."}), 404
            portrait_path = raw_path

        if not portrait_path:
            return jsonify({"error": "Bitte wähle zuerst ein Porträtbild aus."}), 400

        resolved_path = storage.resolve_path(portrait_path)
        if not resolved_path.is_file():
            return jsonify({"error": "Kein gültiges Porträtbild zum Analysieren vorhanden. Bitte lade zuerst ein Bild hoch."}), 400

        target_lang = (user.language or "en").strip().lower()[:2]
        from domain.translation.models import LANGUAGE_METADATA
        lang_label = LANGUAGE_METADATA.get(target_lang, {}).get("label", target_lang)
        settings = SettingsRepository().get_settings()
        from shared.i18n import t as core_t
        prompt = core_t(settings.prompts.vision_persona_prompt, target_lang)
        if target_lang != "en":
            prompt = f"{prompt.strip()}\nRespond strictly in {lang_label} ({target_lang})."

        llm = get_llm_provider(settings)
        appearance = service.extract_appearance_from_image(
            image_path=resolved_path,
            vision_provider=llm,
            vision_model=settings.tasks.vision_model,
            prompt=prompt,
        )
        return jsonify({"appearance": appearance, "portrait_path": portrait_path})
    except AimoError:
        return jsonify({"error": "Bildanalyse fehlgeschlagen."}), 502
    except Exception:
        return jsonify({"error": "Bildanalyse fehlgeschlagen."}), 502


@api_personas_bp.route("/<int:persona_id>/analyze", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def analyze_persona_portrait(persona_id: int):
    user = get_current_user()
    repo = PersonaRepository()
    service = PersonaService()
    storage = FileStorage()

    persona = repo.get_by_id(persona_id)
    if persona is None or persona.user_id != user.id:
        return jsonify({"error": "Persona not found."}), 404

    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    target_lang = (user.language or "en").strip().lower()[:2]
    from domain.translation.models import LANGUAGE_METADATA
    lang_label = LANGUAGE_METADATA.get(target_lang, {}).get("label", target_lang)
    prompt = settings.prompts.vision_persona_prompt
    if target_lang != "en":
        prompt = f"{prompt.strip()}\nRespond strictly in {lang_label} ({target_lang})."

    try:
        resolved_path = storage.resolve_path(persona.portrait_path)
        appearance = service.analyze_appearance(
            persona=persona,
            vision_provider=llm,
            vision_model=settings.tasks.vision_model,
            prompt=prompt,
            resolved_image_path=resolved_path,
        )
        repo.update(persona)
        return jsonify({"appearance": appearance})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502


@api_personas_bp.route("/<int:persona_id>/default", methods=["POST"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def set_default_persona(persona_id: int):
    user = get_current_user()
    repo = PersonaRepository()
    persona = repo.get_by_id(persona_id)
    if persona is None or persona.user_id != user.id:
        return jsonify({"error": "Persona not found."}), 404
    repo.set_default(user.id, persona_id)
    return jsonify({"status": "ok", "default_persona_id": persona_id})


@api_personas_bp.route("/<int:persona_id>", methods=["DELETE"])
@require_permission(FunctionPermission.PERSONA_MANAGE)
def delete_persona(persona_id: int):
    user = get_current_user()
    repo = PersonaRepository()
    service = PersonaService()

    persona = repo.get_by_id(persona_id)
    if persona is None or persona.user_id != user.id:
        return jsonify({"error": "Persona not found."}), 404

    try:
        in_use = repo.is_used_in_any_session(persona_id)
        service.delete_persona(persona, has_active_chats=in_use)
        repo.delete(persona_id)
        return jsonify({"deleted": True})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 409
