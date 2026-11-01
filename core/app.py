import os
from pathlib import Path
import sys

CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from flask import Flask, jsonify, request

from application.api import (
    api_admin_bp,
    api_characters_bp,
    api_chat_bp,
    api_lorebooks_bp,
    api_personas_bp,
    api_worldinfo_bp,
)
from application.api.auth import get_expected_client_key, verify_client_key
from infrastructure.database import init_db
from infrastructure.storage.file_storage import FileStorage
from shared.config import Config


def create_core_app(config_class: type[Config] = Config) -> Flask:
    client_key = get_expected_client_key()
    if not client_key:
        raise RuntimeError(
            "CLIENT_KEY environment variable is required to start the aimo core service."
        )

    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = config_class.SECRET_KEY

    init_db()
    FileStorage(config_class.UPLOAD_DIR)

    app.register_blueprint(api_admin_bp)
    app.register_blueprint(api_characters_bp)
    app.register_blueprint(api_chat_bp)
    app.register_blueprint(api_lorebooks_bp)
    app.register_blueprint(api_personas_bp)
    app.register_blueprint(api_worldinfo_bp)

    @app.before_request
    def enforce_client_key_on_rest():
        if request.method == "OPTIONS":
            return None
        ok, err_resp = verify_client_key()
        if not ok:
            return err_resp
        return None

    @app.route("/api/ping", methods=["GET"])
    def ping():
        return jsonify({"status": "ok", "service": "aimo-core"})

    return app


create_app = create_core_app

if __name__ == "__main__":
    application = create_core_app()
    host = os.getenv("AIMO_CORE_HOST", os.getenv("AIMO_HOST", "127.0.0.1"))
    port = int(os.getenv("AIMO_CORE_PORT", os.getenv("AIMO_PORT", "5001")))
    debug = os.getenv("AIMO_DEBUG", "false").lower() in ("1", "true", "yes")
    application.run(host=host, port=port, debug=debug, threaded=True)
