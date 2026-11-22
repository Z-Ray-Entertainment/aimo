from __future__ import annotations

import gzip
import hashlib
import hmac
import threading
import time
from typing import Any
from urllib.parse import urlparse

from flask import Flask, request


def is_debug_enabled(raw_val: str | None) -> bool:
    return (raw_val or "").strip().lower() in ("1", "true", "yes", "on")


def validate_secret_key(secret_key: str | None, dev_default: str, *, debug: bool = False) -> None:
    cleaned = (secret_key or "").strip()
    if not cleaned:
        raise RuntimeError("AIMO_SECRET_KEY must not be empty.")
    if not debug and cleaned == dev_default:
        raise RuntimeError(
            "Refusing to start in non-debug mode with the default development AIMO_SECRET_KEY."
        )


def sign_user_id(user_id: int, secret_key: str, timestamp: int | None = None) -> tuple[str, str]:
    ts = str(int(time.time()) if timestamp is None else int(timestamp))
    payload = f"{int(user_id)}:{ts}".encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return ts, sig


def is_safe_redirect_target(target: str | None, expected_host: str) -> bool:
    if not target or not isinstance(target, str):
        return False
    cleaned = target.strip()
    if not cleaned:
        return False
    parsed = urlparse(cleaned)
    if parsed.scheme or parsed.netloc:
        return parsed.scheme in ("http", "https") and parsed.netloc == expected_host
    return cleaned.startswith("/") and not cleaned.startswith("//")


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 10, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            history = [ts for ts in self._attempts.get(key, []) if ts > cutoff]
            self._attempts[key] = history
            if len(history) >= self.max_attempts:
                retry_after = max(1, int(self.window_seconds - (now - history[0])))
                return False, retry_after
            return True, 0

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            history = [ts for ts in self._attempts.get(key, []) if ts > cutoff]
            history.append(now)
            self._attempts[key] = history

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


def register_gzip_compression(app: Flask, min_size: int = 500) -> None:
    @app.after_request
    def _compress_response(response):
        if (
            response.status_code < 200
            or response.status_code >= 300
            or response.direct_passthrough
            or "Content-Encoding" in response.headers
            or "gzip" not in (request.headers.get("Accept-Encoding") or "").lower()
        ):
            return response
        content_type = (response.content_type or "").lower()
        if "text/event-stream" in content_type or not any(
            t in content_type for t in ("text/", "application/json", "application/javascript", "image/svg+xml")
        ):
            return response
        data = response.get_data()
        if len(data) < min_size:
            return response
        compressed = gzip.compress(data, compresslevel=6)
        if len(compressed) >= len(data):
            return response
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"
        return response


class RequestDataParser:
    @staticmethod
    def to_opt_int(data: Any, key: str) -> int | None:
        if not hasattr(data, "get"):
            return None
        raw = data.get(key)
        if raw in (None, "", "0", 0, "world", "none"):
            return None
        try:
            parsed = int(raw)
            return parsed if parsed > 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def to_int(
        data: Any,
        key: str,
        default: int = 0,
        min_val: int | None = None,
        max_val: int | None = None,
    ) -> int:
        raw = data.get(key, default) if hasattr(data, "get") else default
        try:
            res = int(raw)
        except (ValueError, TypeError):
            res = default
        if min_val is not None:
            res = max(min_val, res)
        if max_val is not None:
            res = min(max_val, res)
        return res

    @staticmethod
    def to_bool(data: Any, key: str, default: bool = False) -> bool:
        if not hasattr(data, "get"):
            return default
        val = data.get(key)
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    @staticmethod
    def to_str(data: Any, key: str, default: str = "") -> str:
        if not hasattr(data, "get"):
            return default
        val = data.get(key)
        return str(val).strip() if val is not None else default
