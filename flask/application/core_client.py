import os
from typing import Any

from flask import Blueprint, Response, jsonify, request, session, stream_with_context
import requests

from shared.config import Config

core_proxy_bp = Blueprint("core_proxy", __name__)


def get_core_base_url() -> str:
    return (os.getenv("AIMO_CORE_URL") or Config.CORE_URL or "http://127.0.0.1:5001").rstrip("/")


def get_client_key() -> str:
    return (os.getenv("CLIENT_KEY") or Config.CLIENT_KEY or "").strip()


def build_core_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    client_key = get_client_key()
    if client_key:
        headers["X-Client-Key"] = client_key
    user_id = session.get("user_id")
    if user_id is not None:
        headers["X-User-Id"] = str(user_id)
    if extra_headers:
        headers.update(extra_headers)
    return headers


@core_proxy_bp.route(
    "/api/<path:subpath>",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
def proxy_to_core(subpath: str) -> Any:
    core_url = f"{get_core_base_url()}/api/{subpath}"
    headers = build_core_headers()

    for hdr in ("Content-Type", "Accept"):
        val = request.headers.get(hdr)
        if val:
            headers[hdr] = val

    is_sse = (
        subpath.endswith("/stream")
        or subpath.endswith("/models/pull")
        or "text/event-stream" in (request.headers.get("Accept") or "")
    )

    try:
        upstream = requests.request(
            method=request.method,
            url=core_url,
            params=request.args.to_dict(flat=False),
            data=request.get_data(),
            headers=headers,
            cookies=request.cookies,
            stream=is_sse,
            timeout=(10, 600) if is_sse else (10, 300),
        )
    except requests.exceptions.Timeout as exc:
        return jsonify({"error": f"Core service timeout: {exc}", "is_timeout": True}), 504
    except requests.RequestException as exc:
        return jsonify({"error": f"Core service unreachable: {exc}", "is_backend_down": True}), 502

    content_type = upstream.headers.get("Content-Type", "application/json")
    if is_sse or "text/event-stream" in content_type:
        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        return Response(
            stream_with_context(generate()),
            status=upstream.status_code,
            content_type=content_type,
        )

    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=content_type,
    )
