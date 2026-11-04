from flask import Blueprint, render_template

from application.auth.decorators import get_current_user, require_auth

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("", methods=["GET"])
@require_auth
def index():
    user = get_current_user()
    return render_template("settings/index.html", current_user=user)
