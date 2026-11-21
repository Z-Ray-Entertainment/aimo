from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from application.auth.forms import LoginForm
from application.ui_helpers import tr
from domain.auth.services import AuthService
from domain.translation.models import Language
from i18n import gettext_noop as _
from infrastructure.repositories.user_repository import UserRepository
from shared.security import LoginRateLimiter, is_safe_redirect_target

auth_bp = Blueprint("auth", __name__)
_login_limiter = LoginRateLimiter(max_attempts=10, window_seconds=60)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    user_repo = UserRepository()
    if user_repo.count_users() == 0:
        return redirect(url_for("setup.first_boot"))

    form = LoginForm.from_request(request.form if request.method == "POST" else {})
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"
        if _login_limiter.is_rate_limited(client_ip):
            flash(tr(_("Too many login attempts. Please wait a moment and try again.")), "error")
            return render_template("auth/login.html", form=form), 429

        auth_service = AuthService()
        user = user_repo.get_by_email(form.email)
        if auth_service.authenticate_with_lookup(user, form.password):
            assert user is not None
            _login_limiter.reset(client_ip)
            session["user_id"] = user.id
            if not user.language:
                detected = request.accept_languages.best_match(
                    [lang.value for lang in Language], default=Language.DE.value
                )
                auth_service.assign_language(user, detected)
                user_repo.update(user)
            raw_next = request.args.get("next")
            next_url = raw_next if is_safe_redirect_target(raw_next) else url_for("overview.index")
            return redirect(next_url)

        _login_limiter.record_failure(client_ip)
        flash(tr(_("Invalid email address or password.")), "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register_disabled():
    abort(403)
