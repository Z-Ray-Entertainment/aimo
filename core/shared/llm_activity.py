from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import threading
import time

_LOCK = threading.Lock()
_ACTIVE_COUNT = 0
_LAST_ACTIVITY_AT = 0.0
DEFAULT_COOLDOWN_SECONDS = 15.0


def touch_interactive_llm() -> None:
    global _LAST_ACTIVITY_AT
    with _LOCK:
        _LAST_ACTIVITY_AT = time.monotonic()


def begin_interactive_llm() -> None:
    global _ACTIVE_COUNT, _LAST_ACTIVITY_AT
    with _LOCK:
        _ACTIVE_COUNT += 1
        _LAST_ACTIVITY_AT = time.monotonic()


def end_interactive_llm() -> None:
    global _ACTIVE_COUNT, _LAST_ACTIVITY_AT
    with _LOCK:
        if _ACTIVE_COUNT > 0:
            _ACTIVE_COUNT -= 1
        _LAST_ACTIVITY_AT = time.monotonic()


def is_interactive_llm_busy(cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> bool:
    with _LOCK:
        if _ACTIVE_COUNT > 0:
            return True
        if _LAST_ACTIVITY_AT <= 0.0:
            return False
        return (time.monotonic() - _LAST_ACTIVITY_AT) < cooldown_seconds


@contextmanager
def interactive_llm_guard() -> Iterator[None]:
    begin_interactive_llm()
    try:
        yield
    finally:
        end_interactive_llm()
