from flask import flash, redirect, render_template, request, url_for

from application.admin.forms import AdminUserForm
from application.admin.views import admin_bp
from application.auth.decorators import require_permission
from application.core_client import core_delete, core_get, core_post, core_put
from application.ui_helpers import tr
from application.view_models import FunctionPermission, wrap_dto
from i18n import gettext_noop as _


@admin_bp.route("/users", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def users_list():
    _, data = core_get("/api/admin/users")
    return render_template("admin/users.html", users=wrap_dto(data.get("users", [])))


@admin_bp.route("/users/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def create_user():
    if request.method == "POST":
        form = AdminUserForm.from_request(request.form)
        status, payload = core_post(
            "/api/admin/users",
            json={
                "username": form.username,
                "email": form.email,
                "password": form.password,
                "language": form.language,
                "preset": form.preset,
                "permissions": form.permissions,
            },
        )
        if status < 400:
            flash(tr(_("User created successfully.")), "success")
            return redirect(url_for("admin.users_list"))
        flash(payload.get("error") or tr(_("Failed to create user.")), "error")
    return render_template("admin/user_form.html", user=None, all_permissions=[p.value for p in FunctionPermission])


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def edit_user(user_id: int):
    if request.method == "POST":
        form = AdminUserForm.from_request(request.form)
        body: dict = {
            "username": form.username,
            "email": form.email,
            "language": form.language,
            "permissions": form.permissions,
        }
        if form.password:
            body["password"] = form.password
        status, payload = core_put(f"/api/admin/users/{user_id}", json=body)
        if status < 400:
            flash(tr(_("User updated successfully.")), "success")
            return redirect(url_for("admin.users_list"))
        flash(payload.get("error") or tr(_("Failed to update user.")), "error")

    status, data = core_get(f"/api/admin/users/{user_id}")
    if status != 200:
        flash(tr(_("User not found.")), "error")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", user=wrap_dto(data), all_permissions=[p.value for p in FunctionPermission])


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def delete_user(user_id: int):
    status, payload = core_delete(f"/api/admin/users/{user_id}")
    if status < 400:
        flash(tr(_("User deleted.")), "success")
    else:
        flash(payload.get("error") or tr(_("Failed to delete user.")), "error")
    return redirect(url_for("admin.users_list"))
