from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, is_admin, require_auth, require_permission
from application.translation_helpers import is_worldinfo_ready_for_language
from domain.permissions.models import FunctionPermission
from domain.worldinfo.services import WorldInfoService
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

api_worldinfo_bp = Blueprint("api_worldinfo", __name__, url_prefix="/api/worldinfo")


@api_worldinfo_bp.route("", methods=["GET"])
@require_auth
def list_worldinfo():
    user = get_current_user()
    uid = user.id if user and user.id else None
    user_lang = (user.language or "en")[:2].lower() if user else "en"
    user_tag = user.creator_tag if user else None
    admin_flag = is_admin()
    repo = WorldInfoRepository()
    trans_repo = TranslationRepository()
    worlds = repo.list_all(uid)
    result = []
    for wi in worlds:
        if wi.id is None:
            continue
        is_editable = bool(uid and wi.is_editable_by_user(uid, admin_flag, user_tag))
        if not is_editable and not is_worldinfo_ready_for_language(wi, user_lang, trans_repo, repo):
            continue
        locations = repo.list_locations(wi.id)
        events = repo.list_events(wi.id)
        result.append(
            {
                "id": wi.id,
                "name": wi.name,
                "icon": wi.icon,
                "visibility": wi.visibility,
                "cover_image_path": wi.cover_image_path,
                "lorebook_id": wi.lorebook_id,
                "locations": [
                    {
                        "id": loc.id,
                        "name": loc.name,
                        "tags": loc.tags,
                        "description": loc.description,
                        "background_image_path": loc.background_image_path,
                        "vision_alt_text": loc.vision_alt_text,
                        "character_id": loc.character_id,
                    }
                    for loc in locations
                ],
                "events": [
                    {
                        "id": ev.id,
                        "location_id": ev.location_id,
                        "title": ev.title,
                        "probability": ev.probability,
                        "one_shot": ev.one_shot,
                        "description": ev.description,
                    }
                    for ev in events
                ],
            }
        )
    return jsonify({"worldinfos": result})


@api_worldinfo_bp.route("", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_CREATE)
def create_worldinfo():
    user = get_current_user()
    assert user is not None and user.id is not None
    data = request.get_json(silent=True) or request.form.to_dict()
    service = WorldInfoService()
    repo = WorldInfoRepository()
    try:
        raw_lb = data.get("lorebook_id")
        lb_id = int(raw_lb) if raw_lb not in (None, "", "0", 0) else None
        wi = service.create_worldinfo(
            user_id=user.id,
            name=data.get("name", ""),
            icon=data.get("icon", "🌐"),
            visibility=data.get("visibility", "private"),
            cover_image_path=data.get("cover_image_path"),
            lorebook_id=lb_id,
        )
        saved = repo.create(wi)
        return jsonify(
            {
                "id": saved.id,
                "name": saved.name,
                "icon": saved.icon,
                "visibility": saved.visibility,
                "cover_image_path": saved.cover_image_path,
                "lorebook_id": saved.lorebook_id,
            }
        ), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_worldinfo_bp.route("/events", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def create_event():
    user = get_current_user()
    assert user is not None and user.id is not None
    data = request.get_json(silent=True) or request.form.to_dict()
    service = WorldInfoService()
    repo = WorldInfoRepository()
    try:
        worldinfo_id = int(data.get("worldinfo_id", 0))
        wi = repo.get_by_id(worldinfo_id)
        if wi is None or not wi.is_editable_by_user(user.id, is_admin(), user.creator_tag):
            return jsonify({"error": "WorldInfo not found."}), 404

        loc_raw = data.get("location_id")
        location_id = int(loc_raw) if loc_raw not in (None, "", "world", "0", 0) else None
        event = service.add_event(
            worldinfo_id=worldinfo_id,
            title=data.get("title", ""),
            description=data.get("description", ""),
            probability=int(data.get("probability", 50)),
            one_shot=bool(data.get("one_shot", False)),
            location_id=location_id,
        )
        saved = repo.add_event(event)
        return jsonify(
            {
                "id": saved.id,
                "worldinfo_id": saved.worldinfo_id,
                "location_id": saved.location_id,
                "title": saved.title,
                "probability": saved.probability,
                "one_shot": saved.one_shot,
                "description": saved.description,
            }
        ), 201
    except (AimoError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_worldinfo_bp.route("/locations/analyze-bg", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def analyze_location_background():
    bg_file = request.files.get("background")
    existing_bg_path = (request.form.get("background_image_path") or (request.get_json(silent=True) or {}).get("background_image_path") or "").strip()

    if (bg_file is None or not bg_file.filename) and not existing_bg_path:
        return jsonify({"error": "No background image provided."}), 400

    storage = FileStorage()
    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)

    try:
        if bg_file and bg_file.filename:
            bg_path = storage.save_background(bg_file.stream, bg_file.filename)
        else:
            bg_path = existing_bg_path

        user = get_current_user()
        target_lang = (user.language if user and user.language else "en").strip().lower()[:2]
        from domain.translation.models import LANGUAGE_METADATA
        lang_label = LANGUAGE_METADATA.get(target_lang, {}).get("label", target_lang)
        resolved = storage.resolve_path(bg_path)
        alt_text = llm.analyze_image(
            image_path=resolved,
            prompt=f"Describe this 16:9 location background atmosphere, architecture, lighting, and scenery concisely in {lang_label} ({target_lang}) for a roleplay setting.",
            model=settings.tasks.vision_model,
        ).strip()
        return jsonify(
            {
                "background_image_path": bg_path,
                "vision_alt_text": alt_text,
                "prompt_question": "Möchtest du die Ortsbeschreibung um die KI-generierte Bildbeschreibung erweitern?",
            }
        )
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_worldinfo_bp.route("/locations/extract-tags", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_EDIT)
def extract_location_tags():
    data = request.get_json(silent=True) or request.form.to_dict()
    description = (data.get("description") or "").strip()
    if not description:
        return jsonify({"error": "Keine Ortsbeschreibung übergeben."}), 400

    settings = SettingsRepository().get_settings()
    llm = get_llm_provider(settings)
    service = WorldInfoService()
    try:
        tags = service.extract_tags_from_description(
            description=description,
            llm_provider=llm,
            model=settings.tasks.roleplay_model,
        )
        return jsonify({"tags": tags, "tags_string": ", ".join(tags)})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_worldinfo_bp.route("/<int:worldinfo_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.WORLDINFO_CREATE)
def duplicate_worldinfo(worldinfo_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = WorldInfoRepository()
    orig = repo.get_by_id(worldinfo_id)
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "WorldInfo not found."}), 404
    if not orig.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        trans_repo = TranslationRepository()
        user_lang = (user.language or "en")[:2].lower()
        if not is_worldinfo_ready_for_language(orig, user_lang, trans_repo, repo):
            return jsonify({"error": "This world is not yet available in your language."}), 403
    copied = repo.duplicate(worldinfo_id, user.id)
    return jsonify({"id": copied.id, "name": copied.name}), 201