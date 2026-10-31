import os

from app import create_app

application = create_app()

if __name__ == "__main__":
    host = os.getenv("AIMO_HOST", "0.0.0.0")
    port = int(os.getenv("AIMO_PORT", "5000"))
    debug = os.getenv("AIMO_DEBUG", "false").lower() in ("1", "true", "yes")
    application.run(host=host, port=port, debug=debug, threaded=True)
