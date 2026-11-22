from application.api.admin import api_admin_bp
from application.api.admin_config import api_admin_config_bp
from application.api.admin_users import api_admin_users_bp
from application.api.auth_routes import api_auth_bp
from application.api.characters import api_characters_bp
from application.api.chat import api_chat_bp
from application.api.lorebooks import api_lorebooks_bp
from application.api.overview import api_overview_bp
from application.api.personas import api_personas_bp
from application.api.settings import api_settings_bp
from application.api.setup import api_setup_bp
from application.api.uploads import api_uploads_bp
from application.api.worldinfo import api_worldinfo_bp

__all__ = [
    "api_admin_bp",
    "api_admin_config_bp",
    "api_admin_users_bp",
    "api_auth_bp",
    "api_characters_bp",
    "api_chat_bp",
    "api_lorebooks_bp",
    "api_overview_bp",
    "api_personas_bp",
    "api_settings_bp",
    "api_setup_bp",
    "api_uploads_bp",
    "api_worldinfo_bp",
]
