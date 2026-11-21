from __future__ import annotations

import base64
from pathlib import Path
from typing import ClassVar

import requests

from domain.settings.services import SettingsService
from shared.exceptions import InfrastructureError


def ensure_response_ok(response: requests.Response, context: str) -> None:
    if response.status_code >= 400:
        detail = response.text.strip()
        raise InfrastructureError(
            f"{context} failed with HTTP {response.status_code}: {detail}"
        )


def decode_utf8_line(raw_line: bytes | str) -> str:
    if isinstance(raw_line, bytes):
        return raw_line.decode("utf-8", errors="replace").strip()
    return str(raw_line).strip()


def encode_image_base64(image_path: Path) -> str:
    resolved_path = Path(image_path).resolve()
    if not resolved_path.is_file():
        raise InfrastructureError(
            f"Image file does not exist: '{resolved_path}'."
        )
    try:
        return base64.b64encode(resolved_path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise InfrastructureError(
            f"Failed to read image file '{resolved_path}': {exc}"
        ) from exc


class UrlBackendConfigMixin:
    DEFAULT_BASE_URL: ClassVar[str] = ""
    URL_FIELD_NAME: ClassVar[str] = "base_url"

    @classmethod
    def get_default_config(cls) -> dict[str, str]:
        return {"base_url": cls.DEFAULT_BASE_URL}

    @classmethod
    def validate_active_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
        clear_secret: bool = False,
    ) -> dict[str, str]:
        raw_url = (submitted.get("base_url") or "").strip() or (existing.get("base_url") or "").strip()
        return {"base_url": SettingsService.validate_url(cls.URL_FIELD_NAME, raw_url)}

    @classmethod
    def validate_inactive_config(
        cls,
        submitted: dict[str, str],
        existing: dict[str, str],
        clear_secret: bool = False,
    ) -> dict[str, str]:
        raw_url = (submitted.get("base_url") or "").strip()
        if raw_url:
            return {"base_url": SettingsService.validate_url(cls.URL_FIELD_NAME, raw_url)}
        return {"base_url": (existing.get("base_url") or "").strip() or cls.DEFAULT_BASE_URL}
