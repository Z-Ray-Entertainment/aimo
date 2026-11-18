import base64
import mimetypes
from pathlib import Path
from typing import Any

import requests

from shared.exceptions import InfrastructureError

DEFAULT_GOOGLE_AI_SAFETY_SETTINGS: list[dict[str, str]] = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


def normalize_google_model_id(model: str) -> str:
    cleaned = (model or "").strip()
    if cleaned.startswith("models/"):
        return cleaned[len("models/") :]
    return cleaned


def build_google_headers(api_key: str) -> dict[str, str]:
    cleaned = (api_key or "").strip()
    if not cleaned:
        raise InfrastructureError("Google AI API-Key ist nicht konfiguriert.")
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": cleaned,
    }


def encode_image_inline_part(image_path: Path) -> dict[str, Any]:
    resolved_path = Path(image_path).resolve()
    if not resolved_path.is_file():
        raise InfrastructureError(
            f"Image file does not exist: '{resolved_path}'."
        )
    mime_type, _ = mimetypes.guess_type(str(resolved_path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"
    try:
        encoded_image = base64.b64encode(resolved_path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise InfrastructureError(
            f"Failed to read image file '{resolved_path}': {exc}"
        ) from exc
    return {
        "inlineData": {
            "mimeType": mime_type,
            "data": encoded_image,
        }
    }


def extract_google_error_detail(response: requests.Response) -> str:
    response.encoding = "utf-8"
    raw_text = (response.text or "").strip()
    try:
        payload = response.json()
    except ValueError:
        return raw_text
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        msg = payload["error"].get("message")
        if msg:
            return str(msg).strip()
    return raw_text


def ensure_google_response_ok(response: requests.Response, context: str) -> None:
    if response.status_code >= 400:
        detail = extract_google_error_detail(response)
        raise InfrastructureError(
            f"{context} failed with HTTP {response.status_code}: {detail}"
        )
