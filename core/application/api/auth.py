from functools import wraps
import hmac
import os
from typing import Any, Callable

from flask import g, jsonify, request, session

from application.auth_context import AuthContext
from domain.auth.models import User
from domain.permissions.models import FunctionPermission, UserPermissions
from shared.config import Config


def get_expected_client_key() -> str:
    return (os.getenv("CLIENT_KEY") or Config.CLIENT_KEY or "").strip()


def extract_request_client_key() -> str:
    header_key = (
        request.headers.get("X-Client-Key")
        or request.headers.get("X-API-Key")
        or ""
    ).strip()
    if header_key:
        return header_key
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def verify_client_key() -> tuple[bool, Any | None]:
    expected = get_expected_client_key()
    if not expected:
        return False, (
            jsonify({"error": "Server misconfigured: CLIENT_KEY environment variable is not set."}),
            500,
        )
    provided = extract_request_client_key()
    if not provided or not hmac.compare_digest(provided, expected):
        return False, (
            jsonify({"error": "Invalid or missing CLIENT_KEY in request header."}),
            401,
        )
    return True, None


get_current_user = AuthContext.get_current_user
get_current_permissions = AuthContext.get_current_permissions
has_perm = AuthContext.has_permission
is_admin = AuthContext.is_admin


def require_auth(view_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        ok, err_resp = verify_client_key()
        if not ok:
            return err_resp
        user = get_current_user()
        if user is None:
            return jsonify({"error": "Authentication required."}), 401
        return view_func(*args, **kwargs)

    return wrapped


def require_permission(permission: str | FunctionPermission) -> Callable[..., Any]:
    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            ok, err_resp = verify_client_key()
            if not ok:
                return err_resp
            user = get_current_user()
            if user is None:
                return jsonify({"error": "Authentication required."}), 401
            if not has_perm(permission):
                return jsonify({"error": f"Missing permission: {permission}"}), 403
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
