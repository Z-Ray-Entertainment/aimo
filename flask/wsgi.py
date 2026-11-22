import os
from pathlib import Path
import sys

FLASK_DIR = Path(__file__).resolve().parent
if str(FLASK_DIR) not in sys.path:
    sys.path.insert(0, str(FLASK_DIR))

from app import create_webui_app
from security import is_debug_enabled

application = create_webui_app()

if __name__ == "__main__":
    host = os.getenv("AIMO_HOST", "0.0.0.0")
    port = int(os.getenv("AIMO_PORT", "5000"))
    debug = is_debug_enabled(os.getenv("AIMO_DEBUG"))
    application.run(host=host, port=port, debug=debug, threaded=True)
