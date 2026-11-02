from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, require_auth, require_permission
from application.lorebooks.forms import LorebookEntryForm
from domain.lorebooks.services import LorebookService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.translation_repository import TranslationRepository
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
            visibility=request.form.get("visibility", "private"),
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
    user = get_current_user()
    assert user is not None and user.id is not None

    repo = LorebookRepository()
    service = LorebookService()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_visible_to_user(user.id, user.is_initial_admin):
        flash("Lorebook nicht gefunden.", "error")
        return redirect(url_for("overview.index"))

    is_editable = lorebook.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag)
    is_author = (lorebook.user_id == user.id or user.is_initial_admin)

    if request.method == "POST":
        if not is_editable:
            flash("Zugriff verweigert: Du kannst nur deine eigenen Lorebooks oder für dich freigegebene Kreationen bearbeiten.", "error")
            return redirect(url_for("overview.index"))
        try:
            collaborator_tags = None
            if is_author and "collaborator_creator_tags" in request.form:
                raw_collab = request.form.get("collaborator_creator_tags", "")
                collaborator_tags = [t.strip().lower() for t in raw_collab.split(",") if t.strip()]

            service.update_lorebook(
                lorebook=lorebook,
                name=request.form.get("name", lorebook.name),
                description=request.form.get("description", lorebook.description),
                visibility=request.form.get("visibility", lorebook.visibility),
                collaborator_creator_tags=collaborator_tags,
            )
            lorebook = repo.update(lorebook)
            flash("Lorebook aktualisiert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")

    entries = repo.list_entries(lorebook_id, user_id=user.id, is_admin=user.is_initial_admin)
    trans_repo = TranslationRepository()
    entry_translations = {
        e.id: trans_repo.get_entity_translations_map("lorebook_entry", e.id)
        for e in entries
        if e.id is not None
    }
    valid_tabs = ("info", "entries", "collab")
    active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
    if active_tab not in valid_tabs:
        active_tab = "info"

    return render_template(
        "lorebooks/detail.html",
        lorebook=lorebook,
        is_editable=is_editable,
        is_author=is_author,
        entries=entries,
        active_tab=active_tab,
        entry_translations=entry_translations,
    )


@lorebooks_bp.route("/<int:lorebook_id>/duplicate", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def duplicate_lorebook(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    orig = repo.get_by_id(lorebook_id)
    if orig is None or not orig.is_visible_to_user(user.id, user.is_initial_admin):
        flash("Lorebook nicht gefunden.", "error")
        return redirect(url_for("overview.index", tab="lorebooks"))
    copied = repo.duplicate(lorebook_id, user.id)
    flash(f"Kopie '{copied.name}' erfolgreich angelegt.", "success")
    return redirect(url_for("lorebooks.detail", lorebook_id=copied.id))


@lorebooks_bp.route("/<int:lorebook_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_DELETE)
def delete_lorebook(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_deletable_by_user(user.id, user.is_initial_admin):
        flash("Lorebook nicht gefunden oder keine Berechtigung zum Löschen.", "error")
        return redirect(url_for("overview.index", tab="lorebooks"))
    repo.delete(lorebook_id)
    flash("Lorebook gelöscht.", "success")
    return redirect(url_for("overview.index", tab="lorebooks"))


@lorebooks_bp.route("/<int:lorebook_id>/entries/add", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def add_entry(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("Lorebook nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    form = LorebookEntryForm.from_request(request.form)
    service = LorebookService()
    try:
        entry = service.add_entry(
            lorebook_id=lorebook_id,
            title=form.title,
            tags=form.tags,
            content=form.content,
            visibility=form.visibility,
        )
        saved_entry = repo.add_entry(entry)
        TranslationRepository().save_field_variants_json(
            "lorebook_entry", saved_entry.id, "content", request.form.get("i18n_content")
        )
        flash(f"Eintrag '{entry.title}' hinzugefügt.", "success")
    except AimoError as exc:
        flash(str(exc), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id, tab="entries"))


@lorebooks_bp.route("/<int:lorebook_id>/entries/<int:entry_id>/edit", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def edit_entry(lorebook_id: int, entry_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("Lorebook nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    form = LorebookEntryForm.from_request(request.form)
    service = LorebookService()
    entry = repo.get_entry(entry_id)
    if entry is not None and entry.lorebook_id == lorebook_id:
        try:
            service.update_entry(entry, form.title, form.tags, form.content, visibility=form.visibility)
            repo.update_entry(entry)
            TranslationRepository().save_field_variants_json(
                "lorebook_entry", entry.id, "content", request.form.get("i18n_content")
            )
            flash("Eintrag gespeichert.", "success")
        except AimoError as exc:
            flash(str(exc), "error")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id, tab="entries"))


@lorebooks_bp.route("/<int:lorebook_id>/entries/<int:entry_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def delete_entry(lorebook_id: int, entry_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_editable_by_user(user.id, user.is_initial_admin, user.creator_tag):
        flash("Lorebook nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for("overview.index"))

    repo.delete_entry(entry_id)
    flash("Eintrag gelöscht.", "success")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id, tab="entries"))
