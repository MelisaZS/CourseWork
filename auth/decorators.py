"""Flask helpers for login and role checks.

    @app.route("/admin")
    @role_required("admin")
    def admin(): ...

The logged-in user is kept in the Flask session as {"id", "username", "role"}.
"""

from functools import wraps

from flask import redirect, render_template, request, session, url_for


def current_user():
    """The logged-in user dict, or None."""
    return session.get("user")


def is_safe_next(target):
    """Only allow redirects to paths on this site (blocks //evil.com and http://...)."""
    return bool(target) and target.startswith("/") and not target.startswith("//") and "\\" not in target


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapper


def role_required(*roles):
    """Allow the view only for the given roles. Not logged in -> login page, wrong role -> 403."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
            if user.get("role") not in roles:
                return render_template("forbidden.html", user=user), 403
            return view(*args, **kwargs)

        return wrapper

    return decorator
