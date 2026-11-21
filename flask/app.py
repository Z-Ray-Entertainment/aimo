import os
from pathlib import Path
import sys

FLASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FLASK_DIR.parent
CORE_DIR = PROJECT_ROOT / "core"

for path_entry in (str(CORE_DIR), str(FLASK_DIR)):
    if path_entry in sys.path:
        sys.path.remove(path_entry)
    sys.path.insert(0, path_entry)

from flask import Flask, abort, g, jsonify, redirect, request, send_from_directory, url_for
from urllib.parse import urlparse

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
from application.core_client import core_proxy_bp
from application.lorebooks import lorebooks_bp
from application.overview import overview_bp
from application.personas import personas_bp
from application.settings import settings_bp
from application.setup import setup_bp
from application.ui_helpers import get_safe_back_url, render_new_button
from application.worldinfo import worldinfo_bp
from domain.translation.models import LANGUAGE_METADATA
from infrastructure.database import init_db
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.storage.file_storage import FileStorage
from shared.config import Config
from shared.exceptions import InfrastructureError
from shared.http_compression import register_gzip_compression
from shared.security import is_debug_enabled, validate_secret_key
from asset_minifier import ensure_minified_assets
from i18n import ensure_compiled_locales, get_text_direction, get_translator, normalize_language


def create_webui_app(config_class: type[Config] = Config) -> Flask:
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
    init_db()
    FileStorage(config_class.UPLOAD_DIR)

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
        if use_minified_assets:
            min_dir = FLASK_DIR / "static" / ".min" / subdir
            if (min_dir / filename).is_file():
                return send_from_directory(str(min_dir), filename, max_age=86400)
        return send_from_directory(str(FLASK_DIR / "static" / subdir), filename, max_age=86400)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        user = get_current_user()
        if user is None:
            settings = SettingsRepository().get_settings()
            default_bg = (settings.default_backdrop_path or "").strip() if settings else ""
            if not default_bg or filename != default_bg:
                abort(401)
        storage = FileStorage(config_class.UPLOAD_DIR)
        try:
            resolved = storage.resolve_path(filename)
        except InfrastructureError:
            abort(404)
        if not resolved.is_file():
            return send_from_directory(str(FLASK_DIR / "static" / "img"), "cover.svg", max_age=86400)
        rel = resolved.relative_to(storage.base_upload_dir)
        return send_from_directory(str(storage.base_upload_dir), str(rel), max_age=86400)

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
                abort(403)
        return None

    @app.before_request
    def load_user_and_check_first_boot():
        if request.path.startswith("/static/") or request.path.startswith("/uploads/"):
            return None

        user_repo = UserRepository()
        total_users = user_repo.count_users()
        if total_users == 0:
            if not request.path.startswith("/setup"):
                return redirect(url_for("setup.first_boot"))
            return None

        user = get_current_user()
        get_current_permissions()
        if user is not None and user.language:
            g.ui_language = normalize_language(user.language, default="en")
        else:
            best_lang = request.accept_languages.best_match(list(LANGUAGE_METADATA.keys()))
            g.ui_language = normalize_language(best_lang, default="en")
        if user is not None and user.id is not None and not request.path.startswith("/api/"):
            persona_repo = PersonaRepository()
            trans_repo = TranslationRepository()
            personas = persona_repo.list_for_user(user.id)
            g.default_persona = next(
                (p for p in personas if p.is_default), personas[0] if personas else None
            )
            persona_items = []
            for p in personas:
                p_trans = (
                    trans_repo.get_entity_translations_map("persona", p.id) if p.id else {}
                )
                persona_items.append(
                    {
                        "persona": p,
                        "in_use": persona_repo.is_used_in_any_session(p.id) if p.id else False,
                        "i18n_description": p_trans.get("description", {}),
                        "i18n_appearance": p_trans.get("appearance", {}),
                    }
                )
            g.persona_items = persona_items
        else:
            g.default_persona = None
            g.persona_items = []
        return None

    @app.context_processor
    def inject_template_helpers():
        settings = getattr(g, "system_settings", None)
        if settings is None:
            try:
                settings = SettingsRepository().get_settings()
                g.system_settings = settings
            except Exception:
                settings = None
        default_bg = settings.default_backdrop_path if settings else None
        aimo_languages = [
            {"code": code, "flag": meta["flag"], "label": meta["label"]}
            for code, meta in LANGUAGE_METADATA.items()
        ]
        from i18n import get_js_translations
        ui_lang = getattr(g, "ui_language", "en")
        current_user = getattr(g, "current_user", None)
        ember_particles_enabled = (
            bool(current_user.ember_particles_enabled)
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
            "aimo_languages": aimo_languages,
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
    debug = os.getenv("AIMO_DEBUG", "false").lower() in ("1", "true", "yes")
    application.run(host=host, port=port, debug=debug, threaded=True)
