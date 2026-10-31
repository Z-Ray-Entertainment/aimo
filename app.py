from flask import Flask, abort, g, redirect, request, send_from_directory, url_for

from application.admin import admin_bp
from application.api import (
    api_admin_bp,
    api_characters_bp,
    api_chat_bp,
    api_lorebooks_bp,
    api_personas_bp,
    api_worldinfo_bp,
)
from application.auth import auth_bp, get_current_permissions, get_current_user, has_perm
from application.characters import characters_bp
from application.chat import chat_bp
from application.lorebooks import lorebooks_bp
from application.overview import overview_bp
from application.personas import personas_bp
from application.setup import setup_bp
from application.worldinfo import worldinfo_bp
from infrastructure.database import init_db
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.storage.file_storage import FileStorage
from shared.config import Config
from shared.exceptions import InfrastructureError


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(config_class.BASE_DIR / "static"),
        template_folder=str(config_class.BASE_DIR / "templates"),
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

    app.register_blueprint(api_admin_bp)
    app.register_blueprint(api_characters_bp)
    app.register_blueprint(api_chat_bp)
    app.register_blueprint(api_lorebooks_bp)
    app.register_blueprint(api_personas_bp)
    app.register_blueprint(api_worldinfo_bp)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        storage = FileStorage(config_class.UPLOAD_DIR)
        try:
            resolved = storage.resolve_path(filename)
        except InfrastructureError:
            abort(404)
        if not resolved.is_file():
            return send_from_directory(str(config_class.BASE_DIR / "static" / "img"), "cover.svg")
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
            personas = persona_repo.list_for_user(user.id)
            g.default_persona = next((p for p in personas if p.is_default), personas[0] if personas else None)
            g.persona_items = [
                {
                    "persona": p,
                    "in_use": persona_repo.is_used_in_any_session(p.id) if p.id else False,
                }
                for p in personas
            ]
        else:
            g.default_persona = None
            g.persona_items = []
        return None

    @app.context_processor
    def inject_template_helpers():
        return {
            "has_perm": has_perm,
        }

    return app
