from functools import wraps
from typing import Any, Callable

from flask import abort, g, jsonify, redirect, request, session, url_for

from application.view_models import FunctionPermission


def get_current_user():
    return getattr(g, "current_user", None)


def get_current_permissions() -> set[str]:
    perms = getattr(g, "current_permissions", None)
    return set(perms) if perms else set()


def has_perm(perm: str | FunctionPermission) -> bool:
    user = get_current_user()
    if user is None:
        return False
    if getattr(user, "is_initial_admin", False):
        return True
    key = perm.value if isinstance(perm, FunctionPermission) else str(perm)
    return key in get_current_permissions()


def is_admin() -> bool:
    user = get_current_user()
    return bool(user and (getattr(user, "is_initial_admin", False) or has_perm(FunctionPermission.ADMIN_ACCESS)))


def has_creator_permission() -> bool:
    return any(
        has_perm(p)
        for p in (
            FunctionPermission.CHARACTER_CREATE,
            FunctionPermission.CHARACTER_EDIT,
            FunctionPermission.LOREBOOK_CREATE,
            FunctionPermission.LOREBOOK_EDIT,
            FunctionPermission.WORLDINFO_CREATE,
            FunctionPermission.WORLDINFO_EDIT,
        )
    )


def require_auth(view_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        user = get_current_user()
        if user is None and not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth.login", next=request.path))
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
