import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = Path(os.getenv("AIMO_DATA_DIR", str(BASE_DIR / "data"))).resolve()
UPLOAD_DIR: Path = Path(os.getenv("AIMO_UPLOAD_DIR", str(BASE_DIR / "uploads"))).resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    UPLOAD_PATH: Path = UPLOAD_DIR

    SECRET_KEY: str = os.getenv("AIMO_SECRET_KEY", "aimo-dev-only-change-in-production")

    DATABASE_PATH: Path = Path(
        os.getenv("AIMO_DATABASE_PATH", str(DATA_DIR / "aimo.db"))
    ).resolve()
    DATABASE_URI: str = os.getenv("AIMO_DATABASE_URI", f"sqlite:///{DATABASE_PATH}")

    DEFAULT_OLLAMA_URL: str = os.getenv("AIMO_OLLAMA_URL", "http://localhost:11434")
    DEFAULT_COMFYUI_URL: str = os.getenv("AIMO_COMFYUI_URL", "http://localhost:8188")
    DEFAULT_SEARXNG_URL: str = os.getenv("AIMO_SEARXNG_URL", "http://localhost:8080")
