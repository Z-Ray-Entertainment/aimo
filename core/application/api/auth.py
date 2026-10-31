from functools import wraps
import hmac
import os
from typing import Any, Callable

from flask import g, jsonify, request, session

from domain.auth.models import User
from domain.permissions.models import FunctionPermission, UserPermissions
from domain.permissions.services import PermissionService
from infrastructure.repositories.user_repository import UserRepository
from shared.config import Config


def get_expected_client_key() -> str:
    return (os.getenv("CLIENT_KEY") or Config.CLIENT_KEY or "").strip()


def extract_request_client_key() -> str:
    header_key = (request.headers.get("X-Client-Key") or "").strip()
    if header_key:
        return header_key
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return (request.args.get("client_key") or "").strip()


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
            jsonify({"error": "Invalid or missing CLIENT_KEY."}),
            401,
        )
    return True, None


def get_current_user() -> User | None:
    if hasattr(g, "current_user"):
        return g.current_user

    raw_uid = (
        request.headers.get("X-User-Id")
        or session.get("user_id")
        or request.args.get("user_id")
    )
    if not raw_uid or not str(raw_uid).isdigit():
        g.current_user = None
        return None

    repo = UserRepository()
    user = repo.get_by_id(int(raw_uid))
    g.current_user = user
    return user


def get_current_permissions() -> UserPermissions:
    if hasattr(g, "current_permissions"):
        return g.current_permissions
    user = get_current_user()
    if user is None or user.id is None:
        perms = UserPermissions(user_id=0, permissions=set())
    else:
        repo = UserRepository()
        perms = repo.get_permissions(user.id)
    g.current_permissions = perms
    return perms


def has_perm(permission: str | FunctionPermission) -> bool:
    user = get_current_user()
    if user is None:
        return False
    if user.is_initial_admin:
        return True
    perms = get_current_permissions()
    return PermissionService().has_permission(perms, permission)


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
