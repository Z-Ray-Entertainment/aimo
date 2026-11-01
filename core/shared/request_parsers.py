from typing import Any


class RequestDataParser:
    """Consolidated parser for extracting and sanitizing values from requests/forms/JSON."""

    @staticmethod
    def to_str(data: Any, key: str, default: str = "", strip: bool = True) -> str:
        if not hasattr(data, "get"):
            return default
        val = data.get(key, default)
        if val is None:
            return default
        s = str(val)
        return s.strip() if strip else s

    @staticmethod
    def to_opt_int(data: Any, key: str, default: int | None = None) -> int | None:
        if not hasattr(data, "get"):
            return default
        raw = data.get(key)
        if raw in (None, "", "none", "0", 0, "world"):
            return default
        try:
            return int(raw)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def to_int(
        data: Any,
        key: str,
        default: int = 0,
        min_val: int | None = None,
        max_val: int | None = None,
    ) -> int:
        if not hasattr(data, "get"):
            res = default
        else:
            raw = data.get(key, default)
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
    def to_float(
        data: Any,
        key: str,
        default: float = 0.0,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float:
        if not hasattr(data, "get"):
            res = default
        else:
            raw = data.get(key, default)
            try:
                res = float(raw)
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
        raw = data.get(key, default)
        if isinstance(raw, bool):
            return raw
        if raw in (None, ""):
            return default
        val_str = str(raw).strip().lower()
        return val_str in ("1", "true", "yes", "on")

    @staticmethod
    def to_int_list(data: Any, key: str) -> list[int]:
        if not hasattr(data, "get"):
            return []
        raw_list = data.getlist(key) if hasattr(data, "getlist") else data.get(key, [])
        if isinstance(raw_list, (str, int)):
            raw_list = [raw_list]
        out: list[int] = []
        for x in raw_list:
            try:
                out.append(int(x))
            except (ValueError, TypeError):
                pass
        return out

    @staticmethod
    def to_str_list(data: Any, key: str) -> list[str]:
        if not hasattr(data, "get"):
            return []
        raw_list = data.getlist(key) if hasattr(data, "getlist") else data.get(key, [])
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        out: list[str] = []
        for x in raw_list:
            s = str(x).strip()
            if s:
                out.append(s)
        return out
