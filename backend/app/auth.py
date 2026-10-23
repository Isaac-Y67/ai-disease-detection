"""Authentication helpers: login protection, role checks, CSRF tokens and safe redirects (Section 5.6.2)."""
import hmac
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, jsonify, redirect, request, session, url_for


def csrf_token():
    """Return this session's security token, creating it on first use."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def check_csrf():
    """Reject a form post whose token does not match the session's token."""
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="Missing or invalid security token. Reload the page and try again.")


def safe_next(target):
    """Allow only same-site relative paths, so a login link can never send a user to another website."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            if request.path.startswith("/predict") or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Allow only users whose role is in `roles`; everyone else gets 403 Forbidden."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user["role_name"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
