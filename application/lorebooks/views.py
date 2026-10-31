from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_auth, require_permission
from application.lorebooks.forms import LorebookEntryForm
from domain.lorebooks.services import LorebookService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.lorebook_repository import LorebookRepository
from shared.exceptions import AimoError

lorebooks_bp = Blueprint("lorebooks", __name__, url_prefix="/lorebooks")


@lorebooks_bp.route("/create", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def create_lorebook():
    user = get_current_user()
    assert user is not None and user.id is not None
    service = LorebookService()
    repo = LorebookRepository()
    try:
        lb = service.create_lorebook(
            user_id=user.id,
            name=request.form.get("name", ""),
            description=request.form.get("description", ""),
        )
        saved = repo.create(lb)
        flash(f"Lorebook '{saved.name}' erstellt.", "success")
        return redirect(url_for("lorebooks.detail", lorebook_id=saved.id))
    except AimoError as exc:
        flash(str(exc), "error")
        return redirect(url_for("overview.index"))


@lorebooks_bp.route("/<int:lorebook_id>", methods=["GET", "POST"])
@require_auth
def detail(lorebook_id: int):
    repo = LorebookRepository()
    service = LorebookService()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None:
        flash("Lorebook nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    if request.method == "POST":
        try:
            service.update_lorebook(
                lorebook=lorebook,
                name=request.form.get("name", lorebook.name),
                description=request.form.get("description", lorebook.description),
            )
            lorebook = repo.update(lorebook)
            flash("Lorebook aktualisiert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    entries = repo.list_entries(lorebook_id)
    return render_template("lorebooks/detail.html", lorebook=lorebook, entries=entries)


@lorebooks_bp.route("/<int:lorebook_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_DELETE)
def delete_lorebook(lorebook_id: int):
    repo = LorebookRepository()
    repo.delete(lorebook_id)
    flash("Lorebook gelöscht.", "success")
    return redirect(url_for("overview.index"))


@lorebooks_bp.route("/<int:lorebook_id>/entries/add", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def add_entry(lorebook_id: int):
    form = LorebookEntryForm.from_request(request.form)
    service = LorebookService()
    repo = LorebookRepository()
    try:
        entry = service.add_entry(
            lorebook_id=lorebook_id,
            title=form.title,
            tags=form.tags,
            content=form.content,
        )
        repo.add_entry(entry)
        flash(f"Eintrag '{entry.title}' hinzugefügt.", "success")
    except AimoError as exc:
        flash(str(exc), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))


@lorebooks_bp.route("/<int:lorebook_id>/entries/<int:entry_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def edit_entry(lorebook_id: int, entry_id: int):
    form = LorebookEntryForm.from_request(request.form)
    service = LorebookService()
    repo = LorebookRepository()
    entry = repo.get_entry(entry_id)
    if entry is not None:
        try:
            service.update_entry(entry, form.title, form.tags, form.content)
            repo.update_entry(entry)
            flash("Eintrag gespeichert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))


@lorebooks_bp.route("/<int:lorebook_id>/entries/<int:entry_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def delete_entry(lorebook_id: int, entry_id: int):
    repo = LorebookRepository()
    repo.delete_entry(entry_id)
    flash("Eintrag gelöscht.", "success")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id))
