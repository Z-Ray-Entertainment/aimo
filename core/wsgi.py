import os
from pathlib import Path
import sys

CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from app import create_core_app

application = create_core_app()

if __name__ == "__main__":
    host = os.getenv("AIMO_CORE_HOST", os.getenv("AIMO_HOST", "127.0.0.1"))
    port = int(os.getenv("AIMO_CORE_PORT", os.getenv("AIMO_PORT", "5001")))
    debug = os.getenv("AIMO_DEBUG", "false").lower() in ("1", "true", "yes")
    application.run(host=host, port=port, debug=debug, threaded=True)
