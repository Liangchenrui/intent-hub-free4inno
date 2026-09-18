"""Static API-code authentication."""

from __future__ import annotations

import hmac
from functools import wraps

from flask import jsonify, request

from intent_hub.config import Config


def require_auth(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        bearer = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        key = bearer or request.headers.get("X-API-Key", "").strip()
        expected = str(Config.AUTH_CODE or "").strip()
        if not expected or not key or not hmac.compare_digest(key, expected):
            return jsonify({
                "success": False,
                "data": None,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication failed",
                    "detail": None,
                },
            }), 401
        return function(*args, **kwargs)

    return wrapped
