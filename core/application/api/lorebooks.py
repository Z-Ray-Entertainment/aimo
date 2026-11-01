from flask import Blueprint, jsonify, request

from application.api.auth import get_current_user, require_auth, require_permission
from domain.lorebooks.services import LorebookService
from domain.permissions.models import FunctionPermission
from domain.settings.models import ModelParameters
from infrastructure.llm.factory import get_llm_provider
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from shared.exceptions import AimoError
from shared.utils import filter_stopwords, parse_tags

api_lorebooks_bp = Blueprint("api_lorebooks", __name__, url_prefix="/api/lorebooks")


@api_lorebooks_bp.route("", methods=["GET"])
@require_auth
def list_lorebooks():
    user = get_current_user()
    uid = user.id if user and user.id else None
    repo = LorebookRepository()
    lorebooks = repo.list_for_user(uid)
    result = []
    for lb in lorebooks:
        if lb.id is None:
            continue
        entries = repo.list_entries(lb.id)
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
    if lb is None or not lb.is_editable_by_user(user.id, user.is_initial_admin):
        return jsonify({"error": "Lorebook not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict()
    service = LorebookService()
    try:
        entry = service.add_entry(
            lorebook_id=lorebook_id,
            title=data.get("title", ""),
            tags=data.get("tags", []),
            content=data.get("content", ""),
        )
        saved = repo.add_entry(entry)
        return jsonify(
            {
                "id": saved.id,
                "lorebook_id": saved.lorebook_id,
                "title": saved.title,
                "tags": saved.tags,
                "content": saved.content,
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
    if lb is None or not lb.is_editable_by_user(user.id, user.is_initial_admin):
        return jsonify({"error": "Lorebook not found."}), 404
    deleted = repo.delete_entry(entry_id)
    return jsonify({"deleted": deleted})


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
        raw_output = llm_provider.generate(
            prompt=prompt,
            model=settings.tasks.assistant_model,
            params=ModelParameters(
                num_ctx=2048,
                temperature=0.3,
                top_p=0.9,
                repeat_penalty=1.1,
            ),
        ).strip()
        tags = parse_tags(raw_output)
        clean_tags = filter_stopwords(tags)
        return jsonify({"tags": clean_tags, "tags_string": ", ".join(clean_tags)})
    except AimoError as exc:
        return jsonify({"error": str(exc)}), 502
