from flask import Blueprint, jsonify, request

from application.auth.decorators import get_current_user, require_auth, require_permission
from domain.lorebooks.services import LorebookService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.lorebook_repository import LorebookRepository
from shared.exceptions import AimoError

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
    data = request.get_json(silent=True) or request.form.to_dict()
    service = LorebookService()
    repo = LorebookRepository()
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
    repo = LorebookRepository()
    deleted = repo.delete_entry(entry_id)
    return jsonify({"deleted": deleted})
