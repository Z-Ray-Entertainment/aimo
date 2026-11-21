import logging
import os
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory, session, stream_with_context
import requests

from config import FlaskConfig
from security import sign_user_id

logger = logging.getLogger(__name__)
core_proxy_bp = Blueprint("core_proxy", __name__)
_HTTP_SESSION = requests.Session()


def get_core_base_url() -> str:
    return (os.getenv("AIMO_CORE_URL") or FlaskConfig.CORE_URL or "http://127.0.0.1:5001").rstrip("/")


def get_client_key() -> str:
    return (os.getenv("CLIENT_KEY") or FlaskConfig.CLIENT_KEY or "").strip()


def build_core_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    client_key = get_client_key()
    if client_key:
        headers["X-Client-Key"] = client_key
    user_id = session.get("user_id")
    if user_id is not None and str(user_id).isdigit():
        uid_int = int(user_id)
        secret = str(current_app.secret_key or FlaskConfig.SECRET_KEY or "")
        ts, sig = sign_user_id(uid_int, secret)
        headers["X-User-Id"] = str(uid_int)
        headers["X-User-Timestamp"] = ts
        headers["X-User-Signature"] = sig
    if extra_headers:
        headers.update(extra_headers)
    return headers


def core_request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    files: Any = None,
    timeout: tuple[float, float] = (5.0, 60.0),
) -> tuple[int, dict[str, Any]]:
    url = f"{get_core_base_url()}{path}"
    try:
        resp = _HTTP_SESSION.request(
            method=method.upper(),
            url=url,
            json=json,
            data=data,
            params=params,
            files=files,
            headers=build_core_headers(),
            timeout=timeout,
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        return resp.status_code, payload if isinstance(payload, dict) else {}
    except requests.exceptions.Timeout:
        logger.warning("Core timeout on %s %s", method, path)
        return 504, {"error": "Core service timeout."}
    except requests.RequestException:
        logger.warning("Core unreachable on %s %s", method, path)
        return 502, {"error": "Core service unreachable."}


def core_get(path: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return core_request("GET", path, params=params)


def core_post(
    path: str,
    *,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: Any = None,
    timeout: tuple[float, float] = (5.0, 120.0),
) -> tuple[int, dict[str, Any]]:
    return core_request("POST", path, json=json, data=data, files=files, timeout=timeout)


def core_put(path: str, *, json: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return core_request("PUT", path, json=json)


def core_delete(path: str) -> tuple[int, dict[str, Any]]:
    return core_request("DELETE", path)


def proxy_upload(filename: str) -> Response:
    url = f"{get_core_base_url()}/api/uploads/{filename}"
    try:
        resp = _HTTP_SESSION.get(
            url,
            headers=build_core_headers(),
            timeout=(5.0, 30.0),
        )
    except requests.RequestException:
        return Response("Core service unreachable.", status=502)

    if resp.status_code == 401:
        return Response("Unauthorized.", status=401)
    if resp.status_code == 404:
        static_img = Path(__file__).resolve().parent.parent / "static" / "img"
        return send_from_directory(str(static_img), "cover.svg", max_age=86400)
    if resp.status_code >= 400:
        return Response(resp.content, status=resp.status_code)

    content_type = resp.headers.get("Content-Type", "application/octet-stream")
    out = Response(resp.content, status=200, content_type=content_type)
    out.headers["Cache-Control"] = "public, max-age=86400"
    return out


@core_proxy_bp.route(
    "/api/<path:subpath>",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
def proxy_to_core(subpath: str) -> Any:
    user_id = session.get("user_id")
    if not user_id or not str(user_id).isdigit():
        return jsonify({"error": "Authentication required."}), 401

    core_url = f"{get_core_base_url()}/api/{subpath}"
    headers = build_core_headers()

    for hdr in ("Content-Type", "Accept"):
        val = request.headers.get(hdr)
        if val:
            headers[hdr] = val

    forwarded_params = {
        k: v for k, v in request.args.to_dict(flat=False).items() if k != "user_id"
    }

    is_sse = (
        subpath.endswith("/stream")
        or subpath.endswith("/models/pull")
        or "text/event-stream" in (request.headers.get("Accept") or "")
    )

    try:
        upstream = _HTTP_SESSION.request(
            method=request.method,
            url=core_url,
            params=forwarded_params,
            data=request.get_data(),
            headers=headers,
            cookies=request.cookies,
            stream=is_sse,
            timeout=(10, 600) if is_sse else (10, 300),
        )
    except requests.exceptions.Timeout:
        logger.warning("Core service timeout while proxying /api/%s", subpath)
        return jsonify({"error": "Core service timeout.", "is_timeout": True}), 504
    except requests.RequestException:
        logger.warning("Core service unreachable while proxying /api/%s", subpath)
        return jsonify({"error": "Core service unreachable.", "is_backend_down": True}), 502

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
