"""Static API-code authentication."""

from __future__ import annotations

import hmac
from functools import wraps

from flask import jsonify, request

from intent_hub.config import Config


def require_auth(function, *, routing=False):
    @wraps(function)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        bearer = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        key = bearer or request.headers.get("X-API-Key", "").strip()
        # Shared route key must not grant access to BUPT management endpoints.
        expected = str((Config.ROUTE_API_KEY if routing else '') or Config.AUTH_CODE or "").strip()
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


def require_route_auth(function):
    return require_auth(function, routing=True)
