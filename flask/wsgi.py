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

from app import create_webui_app

application = create_webui_app()

if __name__ == "__main__":
    host = os.getenv("AIMO_HOST", "0.0.0.0")
    port = int(os.getenv("AIMO_PORT", "5000"))
    debug = os.getenv("AIMO_DEBUG", "false").lower() in ("1", "true", "yes")
    application.run(host=host, port=port, debug=debug, threaded=True)
