import hashlib
import hmac
import threading
import time
from urllib.parse import urlparse


def is_debug_enabled(env_value: str | None) -> bool:
    return (env_value or "false").strip().lower() in ("1", "true", "yes")


def validate_secret_key(secret_key: str, dev_default: str, debug: bool) -> None:
    if debug:
        return
    cleaned = (secret_key or "").strip()
    if not cleaned or cleaned == dev_default:
        raise RuntimeError(
            "AIMO_SECRET_KEY environment variable must be set to a strong non-default secret when AIMO_DEBUG is disabled."
        )


def sign_user_id(user_id: int, secret_key: str, timestamp: int | None = None) -> tuple[str, str]:
    ts = str(int(time.time()) if timestamp is None else int(timestamp))
    payload = f"{int(user_id)}:{ts}".encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return ts, sig


def verify_user_id_signature(
    user_id: str,
    timestamp_str: str,
    signature: str,
    secret_key: str,
    max_age_seconds: int = 300,
) -> bool:
    if not user_id or not user_id.isdigit() or not timestamp_str or not signature or not secret_key:
        return False
    try:
        ts = int(timestamp_str)
    except ValueError:
        return False
    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False
    expected_payload = f"{int(user_id)}:{ts}".encode("utf-8")
    expected_sig = hmac.new(secret_key.encode("utf-8"), expected_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.strip().lower(), expected_sig)


def is_safe_redirect_target(target: str | None) -> bool:
    if not target:
        return False
    cleaned = target.strip()
    if not cleaned.startswith("/") or cleaned.startswith("//") or "\\" in cleaned:
        return False
    parsed = urlparse(cleaned)
    return not parsed.scheme and not parsed.netloc


class LoginRateLimiter:
    """Thread-safe sliding-window rate limiter keyed strictly by client IP."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_rate_limited(self, client_ip: str) -> bool:
        key = (client_ip or "unknown").strip()
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = [t for t in self._attempts.get(key, []) if t > cutoff]
            self._attempts[key] = timestamps
            return len(timestamps) >= self.max_attempts

    def record_failure(self, client_ip: str) -> None:
        key = (client_ip or "unknown").strip()
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = [t for t in self._attempts.get(key, []) if t > cutoff]
            timestamps.append(now)
            self._attempts[key] = timestamps

    def reset(self, client_ip: str) -> None:
        key = (client_ip or "unknown").strip()
        with self._lock:
            self._attempts.pop(key, None)
