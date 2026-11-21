import os
from pathlib import Path
import sys

FLASK_DIR = Path(__file__).resolve().parent
if str(FLASK_DIR) not in sys.path:
    sys.path.insert(0, str(FLASK_DIR))

from urllib.parse import urlparse
from flask import Flask, g, jsonify, redirect, request, session, url_for

from application.admin import admin_bp
from application.auth import (
    auth_bp,
    get_current_permissions,
    get_current_user,
    has_creator_permission,
    has_perm,
)
from application.characters import characters_bp
from application.chat import chat_bp
from application.core_client import core_get, core_proxy_bp, proxy_upload
from application.lorebooks import lorebooks_bp
from application.overview import overview_bp
from application.personas import personas_bp
from application.settings import settings_bp
from application.setup import setup_bp
from application.ui_helpers import get_safe_back_url, render_new_button
from application.view_models import LANGUAGE_METADATA, wrap_dto
from application.worldinfo import worldinfo_bp
from asset_minifier import ensure_minified_assets
from config import FlaskConfig
from i18n import ensure_compiled_locales, get_js_translations, get_text_direction, get_translator, normalize_language
from security import is_debug_enabled, register_gzip_compression, validate_secret_key


def create_webui_app(config_class: type[FlaskConfig] = FlaskConfig) -> Flask:
    is_debug = is_debug_enabled(os.getenv("AIMO_DEBUG"))
    validate_secret_key(
        config_class.SECRET_KEY,
        config_class.DEV_SECRET_KEY_DEFAULT,
        debug=is_debug,
    )

    app = Flask(
        __name__,
        static_folder=str(FLASK_DIR / "static"),
        template_folder=str(FLASK_DIR / "templates"),
    )
    app.config.from_object(config_class)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = bool(config_class.SESSION_COOKIE_SECURE)
    app.secret_key = config_class.SECRET_KEY

    ensure_compiled_locales()
    use_minified_assets = config_class.MINIFY_ASSETS and not is_debug
    if use_minified_assets:
        ensure_minified_assets(FLASK_DIR / "static")

    app.register_blueprint(setup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(characters_bp)
    app.register_blueprint(personas_bp)
    app.register_blueprint(lorebooks_bp)
    app.register_blueprint(worldinfo_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(core_proxy_bp)

    def _jinja_gettext(msgid: str, **kwargs) -> str:
        lang = getattr(g, "ui_language", "en")
        text = get_translator(lang).gettext(msgid)
        return text.format(**kwargs) if kwargs else text

    def _jinja_ngettext(singular: str, plural: str, n: int, **kwargs) -> str:
        lang = getattr(g, "ui_language", "en")
        text = get_translator(lang).ngettext(singular, plural, n)
        return text.format(**kwargs) if kwargs else text

    app.jinja_env.globals["_"] = _jinja_gettext
    app.jinja_env.globals["gettext"] = _jinja_gettext
    app.jinja_env.globals["ngettext"] = _jinja_ngettext

    @app.route("/static/<any('css', 'js'):subdir>/<path:filename>")
    def minified_static_asset(subdir: str, filename: str):
        from flask import send_from_directory

        if use_minified_assets:
            min_dir = FLASK_DIR / "static" / ".min" / subdir
            if (min_dir / filename).is_file():
                return send_from_directory(str(min_dir), filename, max_age=86400)
        return send_from_directory(str(FLASK_DIR / "static" / subdir), filename, max_age=86400)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        return proxy_upload(filename)

    @app.before_request
    def enforce_same_origin_on_mutations():
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return None
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        expected_host = request.host
        source_url = origin or referer
        if source_url:
            parsed = urlparse(source_url)
            if parsed.netloc and parsed.netloc != expected_host:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Cross-origin request blocked."}), 403
                return "Forbidden", 403
        return None

    @app.before_request
    def load_user_and_check_first_boot():
        if request.path.startswith("/static/") or request.path.startswith("/uploads/") or request.path.startswith("/api/"):
            return None

        user_id = session.get("user_id")
        if not user_id and not request.path.startswith("/setup"):
            status_code, status_data = core_get("/api/setup/status")
            if status_code == 200 and status_data.get("first_boot_required"):
                return redirect(url_for("setup.first_boot"))

        g.current_user = None
        g.current_permissions = set()
        g.default_persona = None
        g.persona_items = []
        g.system_backdrop_path = None
        g.aimo_languages = [
            {"code": code, "flag": meta["flag"], "label": meta["label"]}
            for code, meta in LANGUAGE_METADATA.items()
        ]

        if user_id and str(user_id).isdigit():
            me_code, me_data = core_get("/api/auth/me")
            if me_code == 200 and me_data.get("user"):
                user_dto = wrap_dto(me_data["user"])
                g.current_user = user_dto
                g.current_permissions = set(me_data.get("permissions", []))
                g.system_backdrop_path = me_data.get("system_backdrop_path")
                if me_data.get("languages"):
                    g.aimo_languages = me_data["languages"]
                personas_raw = me_data.get("personas", [])
                g.persona_items = [
                    {
                        "persona": wrap_dto(p),
                        "in_use": bool(p.get("in_use")),
                        "i18n_description": p.get("i18n_description", {}),
                        "i18n_appearance": p.get("i18n_appearance", {}),
                    }
                    for p in personas_raw
                ]
                default_id = me_data.get("default_persona_id")
                g.default_persona = next(
                    (item["persona"] for item in g.persona_items if item["persona"].id == default_id),
                    g.persona_items[0]["persona"] if g.persona_items else None,
                )
            elif me_code == 401:
                session.pop("user_id", None)

        user = get_current_user()
        if user is not None and getattr(user, "language", ""):
            g.ui_language = normalize_language(user.language, default="en")
        else:
            best_lang = request.accept_languages.best_match(list(LANGUAGE_METADATA.keys()))
            g.ui_language = normalize_language(best_lang, default="en")
        return None

    @app.context_processor
    def inject_template_helpers():
        default_bg = getattr(g, "system_backdrop_path", None)
        ui_lang = getattr(g, "ui_language", "en")
        current_user = getattr(g, "current_user", None)
        ember_particles_enabled = (
            bool(getattr(current_user, "ember_particles_enabled", True))
            if current_user is not None
            else True
        )
        return {
            "has_perm": has_perm,
            "has_creator_permission": has_creator_permission,
            "new_button": render_new_button,
            "get_safe_back_url": get_safe_back_url,
            "system_backdrop_path": default_bg,
            "system_backdrop_url": url_for("uploaded_file", filename=default_bg) if default_bg else url_for("static", filename="img/cover.svg"),
            "ui_language": ui_lang,
            "ui_dir": get_text_direction(ui_lang),
            "aimo_languages": getattr(g, "aimo_languages", []),
            "aimo_js_i18n": get_js_translations(ui_lang),
            "ember_particles_enabled": ember_particles_enabled,
        }

    @app.errorhandler(403)
    def handle_forbidden(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden."}), 403
        return "Forbidden", 403

    @app.errorhandler(404)
    def handle_not_found(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found."}), 404
        return "Not Found", 404

    @app.errorhandler(500)
    def handle_internal_error(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error."}), 500
        return "Internal Server Error", 500

    if config_class.GZIP_ENABLED:
        register_gzip_compression(app, min_size=config_class.GZIP_MIN_BYTES)

    return app


create_app = create_webui_app

if __name__ == "__main__":
    application = create_webui_app()
    host = os.getenv("AIMO_HOST", "0.0.0.0")
    port = int(os.getenv("AIMO_PORT", "5000"))
    debug = is_debug_enabled(os.getenv("AIMO_DEBUG"))
    application.run(host=host, port=port, debug=debug, threaded=True)
