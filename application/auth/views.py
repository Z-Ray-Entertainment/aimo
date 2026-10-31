from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from application.auth.forms import LoginForm
from domain.auth.services import AuthService
from infrastructure.repositories.user_repository import UserRepository

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    user_repo = UserRepository()
    if user_repo.count_users() == 0:
        return redirect(url_for("setup.first_boot"))

    form = LoginForm.from_request(request.form if request.method == "POST" else {})
    if request.method == "POST":
        auth_service = AuthService()
        user = user_repo.get_by_email(form.email)
        if user is not None and auth_service.authenticate_user(user, form.password):
            session["user_id"] = user.id
            next_url = request.args.get("next") or url_for("overview.index")
            return redirect(next_url)
        flash("Ungültige E-Mail-Adresse oder Passwort.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register_disabled():
    abort(403)
