from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.auth.decorators import get_current_user, is_admin, require_auth, require_permission
from application.lorebooks.forms import LorebookEntryForm
from application.ui_helpers import tr
from i18n import gettext_noop as _
from domain.lorebooks.services import LorebookService
from domain.permissions.models import FunctionPermission
from infrastructure.repositories.lorebook_repository import LorebookRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from shared.exceptions import AimoError

lorebooks_bp = Blueprint("lorebooks", __name__, url_prefix="/lorebooks")


@lorebooks_bp.route("/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.LOREBOOK_CREATE)
def new_lorebook():
    user = get_current_user()
    assert user is not None and user.id is not None
    service = LorebookService()
    repo = LorebookRepository()
    form_data = {
        "name": "",
        "description": "",
        "visibility": "private",
        "is_proper_noun": False,
    }
    if request.method == "POST":
        form_data = {
            "name": request.form.get("name", ""),
            "description": request.form.get("description", ""),
            "visibility": request.form.get("visibility", "private"),
            "is_proper_noun": bool(request.form.get("is_proper_noun")),
        }
        try:
            lb = service.create_lorebook(
                user_id=user.id,
                name=form_data["name"],
                description=form_data["description"],
                visibility=form_data["visibility"],
                is_proper_noun=form_data["is_proper_noun"],
            )
            saved = repo.create(lb)
            flash(tr(_("Lorebook '%(name)s' created."), name=saved.name), "success")
            return redirect(url_for("lorebooks.detail", lorebook_id=saved.id))
        except AimoError as exc:
            flash(str(exc), "error")

    return render_template(
        "lorebooks/detail.html",
        lorebook=None,
        form_data=form_data,
        is_editable=True,
        is_author=True,
        entries=[],
        active_tab="info",
        entry_translations={},
    )


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
        flash(tr(_("Lorebook '%(name)s' created."), name=saved.name), "success")
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
    if lorebook is None or not lorebook.is_visible_to_user(user.id, is_admin()):
        flash(tr(_("Lorebook not found.")), "error")
        return redirect(url_for("overview.index"))

    is_editable = lorebook.is_editable_by_user(user.id, is_admin(), user.creator_tag)
    is_author = (lorebook.user_id == user.id or is_admin())

    if request.method == "POST":
        if not is_editable:
            flash(tr(_("Access denied: You can only edit your own lorebooks or creations shared with you.")), "error")
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
                is_proper_noun=bool(request.form.get("is_proper_noun")),
            )
            lorebook = repo.update(lorebook)
            flash(tr(_("Lorebook updated.")), "success")
            active_tab = request.form.get("active_tab") or request.args.get("tab", "info")
            if active_tab not in ("info", "entries", "collab"):
                active_tab = "info"
            return redirect(url_for("lorebooks.detail", lorebook_id=lorebook.id, tab=active_tab))
        except AimoError as exc:
            flash(str(exc), "error")

    entries = repo.list_entries(lorebook_id, user_id=user.id, is_admin=is_admin())
    trans_repo = TranslationRepository()
    user_lang = (user.language or "en")[:2].lower()
    if not is_editable:
        from application.translation_helpers import is_lorebook_ready_for_language

        if not is_lorebook_ready_for_language(lorebook, user_lang, trans_repo):
            flash(tr(_("This lorebook is not yet available in your language.")), "warning")
            return redirect(url_for("overview.index", tab="lorebooks"))
        if not getattr(lorebook, "is_proper_noun", False):
            lorebook.name = trans_repo.get_localized_field("lorebook", lorebook.id, "name", user_lang, lorebook.name)
        lorebook.description = trans_repo.get_localized_field(
            "lorebook", lorebook.id, "description", user_lang, lorebook.description
        )
        for e in entries:
            if e.id is not None:
                if not getattr(e, "is_proper_noun", False):
                    e.title = trans_repo.get_localized_field("lorebook_entry", e.id, "title", user_lang, e.title)
                e.content = trans_repo.get_localized_field("lorebook_entry", e.id, "content", user_lang, e.content)
                raw_tags = trans_repo.get_localized_field("lorebook_entry", e.id, "tags", user_lang, "")
                if raw_tags:
                    e.tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
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
    if orig is None or not orig.is_visible_to_user(user.id, is_admin()):
        flash(tr(_("Lorebook not found.")), "error")
        return redirect(url_for("overview.index", tab="lorebooks"))
    copied = repo.duplicate(lorebook_id, user.id)
    flash(tr(_("Copy '%(name)s' created successfully."), name=copied.name), "success")
    return redirect(url_for("lorebooks.detail", lorebook_id=copied.id))


@lorebooks_bp.route("/<int:lorebook_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_DELETE)
def delete_lorebook(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_deletable_by_user(user.id, is_admin()):
        flash(tr(_("Lorebook not found or no permission to delete.")), "error")
        return redirect(url_for("overview.index", tab="lorebooks"))
    repo.delete(lorebook_id)
    flash(tr(_("Lorebook deleted.")), "success")
    return redirect(url_for("overview.index", tab="lorebooks"))


@lorebooks_bp.route("/<int:lorebook_id>/entries/add", methods=["POST"])
@require_permission(FunctionPermission.LOREBOOK_EDIT)
def add_entry(lorebook_id: int):
    user = get_current_user()
    assert user is not None and user.id is not None
    repo = LorebookRepository()
    lorebook = repo.get_by_id(lorebook_id)
    if lorebook is None or not lorebook.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Lorebook not found or no permission.")), "error")
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
            is_proper_noun=form.is_proper_noun,
        )
        saved_entry = repo.add_entry(entry)
        TranslationRepository().save_field_variants_json(
            "lorebook_entry", saved_entry.id, "content", request.form.get("i18n_content")
        )
        flash(tr(_("Entry '%(title)s' added."), title=entry.title), "success")
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
    if lorebook is None or not lorebook.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Lorebook not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    form = LorebookEntryForm.from_request(request.form)
    service = LorebookService()
    entry = repo.get_entry(entry_id)
    if entry is not None and entry.lorebook_id == lorebook_id:
        try:
            service.update_entry(
                entry,
                form.title,
                form.tags,
                form.content,
                visibility=form.visibility,
                is_proper_noun=form.is_proper_noun,
            )
            repo.update_entry(entry)
            TranslationRepository().save_field_variants_json(
                "lorebook_entry", entry.id, "content", request.form.get("i18n_content")
            )
            flash(tr(_("Entry saved.")), "success")
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
    if lorebook is None or not lorebook.is_editable_by_user(user.id, is_admin(), user.creator_tag):
        flash(tr(_("Lorebook not found or no permission.")), "error")
        return redirect(url_for("overview.index"))

    entry = repo.get_entry(entry_id)
    if entry is None or entry.lorebook_id != lorebook_id:
        flash(tr(_("Entry not found.")), "error")
        return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id, tab="entries"))

    repo.delete_entry(entry_id)
    flash(tr(_("Entry deleted.")), "success")
    return redirect(url_for("lorebooks.detail", lorebook_id=lorebook_id, tab="entries"))
