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


def build_google_generate_payload(
    parts: list[dict[str, Any]],
    temperature: float,
    top_p: float,
    max_tokens: int | None = None,
    stop: list[str] | None = None,
    format: str | dict | None = None,
    think: bool | None = None,
) -> dict[str, Any]:
    generation_config: dict[str, Any] = {
        "temperature": float(temperature),
        "topP": float(top_p),
    }
    if max_tokens is not None:
        generation_config["maxOutputTokens"] = int(max_tokens)
    if stop:
        clean_stops = [s for s in stop if isinstance(s, str) and s][:5]
        if clean_stops:
            generation_config["stopSequences"] = clean_stops

    if format == "json":
        generation_config["responseMimeType"] = "application/json"
    elif isinstance(format, dict):
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseJsonSchema"] = format

    if think is False:
        generation_config["thinkingConfig"] = {
            "thinkingLevel": "minimal",
            "includeThoughts": False,
        }
    elif think is True:
        generation_config["thinkingConfig"] = {
            "thinkingLevel": "high",
            "includeThoughts": False,
        }

    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
        "safetySettings": DEFAULT_GOOGLE_AI_SAFETY_SETTINGS,
    }


def extract_text_from_google_response(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict) or part.get("thought") is True:
            continue
        text = part.get("text")
        if text:
            chunks.append(str(text))
    return "".join(chunks)


def check_google_response_blocks(payload: dict[str, Any]) -> None:
    if "error" in payload and isinstance(payload["error"], dict):
        msg = payload["error"].get("message") or str(payload["error"])
        raise InfrastructureError(f"Google AI generation error: {msg}")
    feedback = payload.get("promptFeedback")
    if isinstance(feedback, dict):
        block_reason = feedback.get("blockReason")
        if block_reason:
            raise InfrastructureError(
                f"Google AI blocked the request ({block_reason})."
            )


def check_google_candidate_finish_reason(
    payload: dict[str, Any],
    emitted_any: bool,
) -> None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return
    first = candidates[0] if isinstance(candidates[0], dict) else {}
    finish_reason = str(first.get("finishReason") or "")
    if not emitted_any and finish_reason in (
        "SAFETY",
        "PROHIBITED_CONTENT",
        "SPII",
        "BLOCKLIST",
        "RECITATION",
    ):
        raise InfrastructureError(
            f"Google AI blocked the response (finishReason={finish_reason})."
        )
