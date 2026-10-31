import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CORE_DIR: Path = Path(__file__).resolve().parent.parent
PROJECT_ROOT: Path = CORE_DIR.parent
FLASK_DIR: Path = PROJECT_ROOT / "flask"
BASE_DIR: Path = PROJECT_ROOT


def _resolve_writable_dir(preferred: Path, fallback_name: str) -> Path:
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        if os.access(preferred, os.W_OK):
            return preferred
        try:
            preferred.chmod(0o777)
            if os.access(preferred, os.W_OK):
                return preferred
        except OSError:
            pass
    except OSError:
        pass

    fallback = Path("/tmp/aimo") / fallback_name
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DATA_DIR: Path = _resolve_writable_dir(
    Path(os.getenv("AIMO_DATA_DIR", str(PROJECT_ROOT / "data"))).resolve(),
    "data",
)
UPLOAD_DIR: Path = _resolve_writable_dir(
    Path(os.getenv("AIMO_UPLOAD_DIR", str(PROJECT_ROOT / "uploads"))).resolve(),
    "uploads",
)


class Config:
    BASE_DIR: Path = BASE_DIR
    CORE_DIR: Path = CORE_DIR
    FLASK_DIR: Path = FLASK_DIR
    DATA_DIR: Path = DATA_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    UPLOAD_PATH: Path = UPLOAD_DIR

    SECRET_KEY: str = os.getenv("AIMO_SECRET_KEY", "aimo-dev-only-change-in-production")
    CLIENT_KEY: str = os.getenv("CLIENT_KEY", "")

    CORE_HOST: str = os.getenv("AIMO_CORE_HOST", "127.0.0.1")
    CORE_PORT: int = int(os.getenv("AIMO_CORE_PORT", "5001"))
    CORE_URL: str = os.getenv("AIMO_CORE_URL", f"http://{CORE_HOST}:{CORE_PORT}")

    DATABASE_PATH: Path = Path(
        os.getenv("AIMO_DATABASE_PATH", str(DATA_DIR / "aimo.db"))
    ).resolve()
    DATABASE_URI: str = os.getenv("AIMO_DATABASE_URI", f"sqlite:///{DATABASE_PATH}")

    DEFAULT_OLLAMA_URL: str = os.getenv("AIMO_OLLAMA_URL", "http://localhost:11434")
    DEFAULT_COMFYUI_URL: str = os.getenv("AIMO_COMFYUI_URL", "http://localhost:8188")
    DEFAULT_SEARXNG_URL: str = os.getenv("AIMO_SEARXNG_URL", "http://localhost:8080")
