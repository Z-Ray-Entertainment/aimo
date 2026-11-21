from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from application.auth.forms import LoginForm
from application.core_client import core_get, core_post
from application.ui_helpers import tr
from i18n import gettext_noop as _
from security import LoginRateLimiter, is_safe_redirect_target

auth_bp = Blueprint("auth", __name__)
_login_limiter = LoginRateLimiter(max_attempts=10, window_seconds=60)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    status_code, status_data = core_get("/api/setup/status")
    if status_code == 200 and status_data.get("first_boot_required"):
        return redirect(url_for("setup.first_boot"))

    form = LoginForm.from_request(request.form if request.method == "POST" else {})
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"
        allowed, _retry = _login_limiter.is_allowed(client_ip)
        if not allowed:
            flash(tr(_("Too many login attempts. Please wait a moment and try again.")), "error")
            return render_template("auth/login.html", form=form), 429

        code, payload = core_post(
            "/api/auth/login",
            json={"email": form.email, "password": form.password},
        )
        if code == 200 and payload.get("id"):
            _login_limiter.reset(client_ip)
            session["user_id"] = int(payload["id"])
            raw_next = request.args.get("next")
            next_url = raw_next if is_safe_redirect_target(raw_next, request.host) else url_for("overview.index")
            return redirect(next_url)

        _login_limiter.record_failure(client_ip)
        if code == 429:
            flash(tr(_("Too many login attempts. Please wait a moment and try again.")), "error")
            return render_template("auth/login.html", form=form), 429
        flash(tr(_("Invalid email address or password.")), "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register_disabled():
    abort(403)
