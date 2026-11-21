import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FLASK_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = FLASK_DIR.parent


class FlaskConfig:
    DEV_SECRET_KEY_DEFAULT: str = "aimo-dev-only-change-in-production"
    SECRET_KEY: str = os.getenv("AIMO_SECRET_KEY", DEV_SECRET_KEY_DEFAULT)
    CLIENT_KEY: str = os.getenv("CLIENT_KEY", "")
    CORE_URL: str = os.getenv("AIMO_CORE_URL", "http://127.0.0.1:5001")
    SESSION_COOKIE_SECURE: bool = os.getenv("AIMO_SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
    MINIFY_ASSETS: bool = os.getenv("AIMO_MINIFY_ASSETS", "true").lower() in ("1", "true", "yes")
    GZIP_ENABLED: bool = os.getenv("AIMO_GZIP_ENABLED", "true").lower() in ("1", "true", "yes")
    GZIP_MIN_BYTES: int = int(os.getenv("AIMO_GZIP_MIN_BYTES", "500"))
