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

from flask import Flask, abort, g, redirect, request, send_from_directory, url_for

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
from application.setup import setup_bp
from application.ui_helpers import render_new_button
from application.worldinfo import worldinfo_bp
from infrastructure.database import init_db
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.translation_repository import TranslationRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.storage.file_storage import FileStorage
from shared.config import Config
from shared.exceptions import InfrastructureError


def create_webui_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FLASK_DIR / "static"),
        template_folder=str(FLASK_DIR / "templates"),
    )
    app.config.from_object(config_class)
    app.secret_key = config_class.SECRET_KEY

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
    app.register_blueprint(admin_bp)
    app.register_blueprint(core_proxy_bp)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        storage = FileStorage(config_class.UPLOAD_DIR)
        try:
            resolved = storage.resolve_path(filename)
        except InfrastructureError:
            abort(404)
        if not resolved.is_file():
            return send_from_directory(str(FLASK_DIR / "static" / "img"), "cover.svg")
        rel = resolved.relative_to(storage.base_upload_dir)
        return send_from_directory(str(storage.base_upload_dir), str(rel))

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
        if user is not None and user.id is not None:
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
        return {
            "has_perm": has_perm,
            "has_creator_permission": has_creator_permission,
            "new_button": render_new_button,
            "system_backdrop_path": default_bg,
            "system_backdrop_url": url_for("uploaded_file", filename=default_bg) if default_bg else url_for("static", filename="img/cover.svg"),
        }

    return app


create_app = create_webui_app

if __name__ == "__main__":
    application = create_webui_app()
    host = os.getenv("AIMO_HOST", "0.0.0.0")
    port = int(os.getenv("AIMO_PORT", "5000"))
    debug = os.getenv("AIMO_DEBUG", "false").lower() in ("1", "true", "yes")
    application.run(host=host, port=port, debug=debug, threaded=True)
