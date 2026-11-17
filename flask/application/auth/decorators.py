from functools import wraps
from typing import Any, Callable

from flask import abort, jsonify, redirect, request, url_for

from application.auth_context import AuthContext
from domain.auth.models import User
from domain.permissions.models import FunctionPermission, UserPermissions

get_current_user = AuthContext.get_current_user
get_current_permissions = AuthContext.get_current_permissions
has_perm = AuthContext.has_permission
is_admin = AuthContext.is_admin
has_creator_permission = AuthContext.has_creator_permission


def require_auth(view_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        user = get_current_user()
        if user is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def require_permission(*permissions: str | FunctionPermission) -> Callable[..., Any]:
    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            user = get_current_user()
            if user is None:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required."}), 401
                return redirect(url_for("auth.login", next=request.path))
            if not any(has_perm(p) for p in permissions):
                if request.path.startswith("/api/"):
                    perm_names = ", ".join(str(p) for p in permissions)
                    return jsonify({"error": f"Missing permission: {perm_names}"}), 403
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
