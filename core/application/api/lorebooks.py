from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, is_admin, require_auth, require_permission
from domain.lorebooks.services import LorebookService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from shared.exceptions import AimoError
from shared.llm_activity import interactive_llm_guard
from shared.utils import filter_stopwords, parse_tags

api_lorebooks_bp = Blueprint("api_lorebooks", __name__, url_prefix="/api/lorebooks")


@api_lorebooks_bp.route("", methods=["GET"])
@require_auth
def list_lorebooks():
    user = get_current_user()
    uid = user.id if user and user.id else None
    admin_view = is_admin() if user else False
    repo = LorebookRepository()
    lorebooks = repo.list_for_user(uid)
    result = []
    for lb in lorebooks:
        if lb.id is None:
            continue
        entries = repo.list_entries(lb.id, user_id=uid, is_admin=admin_view)
        result.append(
            {
                "id": lb.id,
                "name": lb.name,
                "description": lb.description,
                "visibility": lb.visibility,
                "entries": [
                    {
                        "id": e.id,
                        "title": e.title,
                        "tags": e.tags,
                        "content": e.content,
                        "visibility": getattr(e, "visibility", "public"),
                    }
                    for e in entries
                ],
            }
        )
    return jsonify({"lorebooks": result})


@api_lorebooks_bp.route("", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def create_lorebook():
    user = get_current_user()
    assert user is not None and user.id is not None
    data = request.get_json(silent=True) or request.form.to_dict()
    service = LorebookService()
    repo = LorebookRepository()
    try:
        lb = service.create_lorebook(
            user_id=user.id,
            name=data.get("name", ""),
            description=data.get("description", ""),
            visibility=data.get("visibility", "private"),
        )
        saved = repo.create(lb)
        return jsonify(
            {
                "id": saved.id,
                "name": saved.name,
                "description": saved.description,
                "visibility": saved.visibility,
            }
        ), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_lorebooks_bp.route("/<int:lorebook_id>/entries", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def add_lorebook_entry(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lb = repo.get_by_id(lorebook_id)
    if lb is None or not lb.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Lorebook not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    service = LorebookService()
    try:
        entry = service.add_entry(
            lorebook_id=lorebook_id,
            title=data.get("title", ""),
            tags=data.get("tags", []),
            content=data.get("content", ""),
            visibility=data.get("visibility", "public"),
        )
        saved = repo.add_entry(entry)
        return jsonify(
            {
                "id": saved.id,
                "lorebook_id": saved.lorebook_id,
                "title": saved.title,
                "tags": saved.tags,
                "content": saved.content,
                "visibility": getattr(saved, "visibility", "public"),
            }
        ), 201
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_lorebooks_bp.route("/entries/<int:entry_id>", methods=["DELETE"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def delete_lorebook_entry(entry_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    entry = repo.get_entry(entry_id)
    if entry is None:
        return jsonify({"error": "Entry not found."}), 404
    lb = repo.get_by_id(entry.lorebook_id)
    if lb is None or not lb.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Lorebook not found."}), 404
    deleted = repo.delete_entry(entry_id)
    return jsonify({"deleted": deleted})


@api_lorebooks_bp.route("/<int:lorebook_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def duplicate_lorebook(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    orig = repo.get_by_id(lorebook_id)
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Lorebook not found."}), 404
    if not orig.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        from application.translation_helpers import is_lorebook_ready_for_language
        from infrastructure.repositories.translation_repository import TranslationRepository

        trans_repo = TranslationRepository()
        user_lang = (user.language or "en")[:2].lower()
        if not is_lorebook_ready_for_language(orig, user_lang, trans_repo, repo):
            return jsonify({"error": "This lorebook is not yet available in your language."}), 403
    copied = repo.duplicate(lorebook_id, user.id)
    return jsonify({"id": copied.id, "name": copied.name}), 201


@api_lorebooks_bp.route("/suggest-tags", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def suggest_tags():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    content = str(data.get("content", "")).strip()

    if not title and not content:
        return jsonify({"tags": [], "tags_string": ""})

    settings = SettingsRepository().get_settings()
    llm_provider = get_llm_provider(settings)

    prompt = (
        "Du bist ein intelligenter Assistent für ein Rollenspiel-Lorebook / You are an assistant for a roleplay lorebook.\n"
        "Analysiere den folgenden Wissenseintrag und extrahiere 4 bis 8 prägnante, relevante Schlagwörter (Tags) auf Deutsch und Englisch. "
        "Diese Tags dienen als Auslöser (Trigger), um diesen Eintrag automatisch in den Chat-Prompt zu laden, sobald der Spieler sie erwähnt.\n"
        "Regeln:\n"
        "- Berücksichtige Eigennamen, Orte, Gruppierungen, Kernbegriffe und markante Synonyme.\n"
        "- Keine generischen Füllwörter oder Satzfragmente.\n"
        "- Antworte AUSSCHLIESSLICH mit einer kommagetrennten Liste kleingeschriebener Tags ohne Aufzählungszeichen, Nummern oder Zusatztext.\n\n"
        f"Titel: {title}\n"
        f"Inhalt / Content:\n{content}\n\n"
        "Tags:"
    )

    try:
        with interactive_llm_guard():
            raw_output = llm_provider.generate(
                prompt=prompt,
                model=settings.tasks.assistant_model,
                params=ModelParameters(
                    num_ctx=2048,
                    temperature=0.3,
                    top_p=0.9,
                    repeat_penalty=1.1,
                ),
                think=False,
            ).strip()
        tags = parse_tags(raw_output)
        clean_tags = filter_stopwords(tags)
        return jsonify({"tags": clean_tags, "tags_string": ", ".join(clean_tags)})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502


@api_lorebooks_bp.route("/<int:lorebook_id>", methods=["GET"])
@require_auth
def get_lorebook_detail(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lb = repo.get_by_id(lorebook_id)
    if lb is None or not lb.is_visible_to_user(user.id, is_admin()):
        return jsonify({"error": "Lorebook not found."}), 404
    entries = repo.list_entries(lorebook_id)
    return jsonify(
        {
            "id": lb.id,
            "user_id": lb.user_id,
            "name": lb.name,
            "description": lb.description,
            "visibility": lb.visibility,
            "origin_language": lb.origin_language,
            "is_proper_noun": lb.is_proper_noun,
            "editable": lb.is_editable_by_user(user.id, is_admin(), user.creator_tag),
            "deletable": lb.is_deletable_by_user(user.id, is_admin()),
            "entries": [
                {
                    "id": e.id,
                    "title": e.title,
                    "tags": e.tags,
                    "content": e.content,
                    "visibility": e.visibility,
                    "is_proper_noun": e.is_proper_noun,
                }
                for e in entries
                if e.is_visible_to_user(lb.user_id, user.id, is_admin())
            ],
        }
    )


@api_lorebooks_bp.route("/<int:lorebook_id>", methods=["PUT"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def update_lorebook_detail(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lb = repo.get_by_id(lorebook_id)
    if lb is None or not lb.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Lorebook not found."}), 404
    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        updated = LorebookService().update_lorebook(
            lb,
            name=data.get("name", lb.name),
            description=data.get("description", lb.description),
            visibility=data.get("visibility", lb.visibility),
            is_proper_noun=bool(data.get("is_proper_noun", lb.is_proper_noun)),
        )
        saved = repo.update(updated)
        return jsonify({"id": saved.id, "name": saved.name})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400


@api_lorebooks_bp.route("/<int:lorebook_id>", methods=["DELETE"])
@require_permission(FunctionPermission.LOREBOOK_DELETE)
def delete_lorebook_detail(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lb = repo.get_by_id(lorebook_id)
    if lb is None or not lb.is_deletable_by_user(user.id, is_admin()):
        return jsonify({"error": "Lorebook not found."}), 404
    return jsonify({"deleted": repo.delete(lorebook_id)})


@api_lorebooks_bp.route("/entries/<int:entry_id>", methods=["PUT"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def update_lorebook_entry(entry_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    entry = repo.get_entry(entry_id)
    if entry is None:
        return jsonify({"error": "Entry not found."}), 404
    lb = repo.get_by_id(entry.lorebook_id)
    if lb is None or not lb.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        return jsonify({"error": "Lorebook not found."}), 404
    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        updated = LorebookService().update_entry(
            entry,
            title=data.get("title", entry.title),
            tags=data.get("tags", entry.tags),
            content=data.get("content", entry.content),
            visibility=data.get("visibility", entry.visibility),
            is_proper_noun=bool(data.get("is_proper_noun", entry.is_proper_noun)),
        )
        saved = repo.update_entry(updated)
        return jsonify({"id": saved.id, "title": saved.title, "tags": saved.tags})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 400
