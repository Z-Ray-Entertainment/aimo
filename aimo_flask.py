#!/usr/bin/env python3
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent
CORE_DIR = PROJECT_ROOT / "core"
FLASK_DIR = PROJECT_ROOT / "flask"


def _wait_for_core(core_url: str, client_key: str, timeout_sec: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_sec
    ping_url = f"{core_url.rstrip('/')}/api/ping"
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(
                ping_url,
                headers={"X-Client-Key": client_key},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def main() -> int:
    client_key = str(uuid.uuid4())

    core_host = os.getenv("AIMO_CORE_HOST", "127.0.0.1")
    core_port = os.getenv("AIMO_CORE_PORT", "5001")
    core_url = os.getenv("AIMO_CORE_URL", f"http://{core_host}:{core_port}")

    webui_host = os.getenv("AIMO_HOST", "0.0.0.0")
    webui_port = os.getenv("AIMO_PORT", "5000")

    env = os.environ.copy()
    env["CLIENT_KEY"] = client_key
    env["AIMO_CORE_HOST"] = core_host
    env["AIMO_CORE_PORT"] = core_port
    env["AIMO_CORE_URL"] = core_url
    env["AIMO_HOST"] = webui_host
    env["AIMO_PORT"] = webui_port

    core_proc = subprocess.Popen(
        [sys.executable, str(CORE_DIR / "wsgi.py")],
        cwd=str(CORE_DIR),
        env=env,
    )

    _wait_for_core(core_url, client_key)

    webui_proc = subprocess.Popen(
        [sys.executable, str(FLASK_DIR / "wsgi.py")],
        cwd=str(FLASK_DIR),
        env=env,
    )

    processes = [core_proc, webui_proc]

    def _shutdown(signum: int, _frame) -> None:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            for proc in processes:
                ret = proc.poll()
                if ret is not None:
                    _shutdown(signal.SIGTERM, None)
                    return ret
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown(signal.SIGINT, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
