"""Single-user bearer-token authentication."""

from __future__ import annotations

import time
import uuid
from functools import wraps

from flask import jsonify, request

from intent_hub.config import Config


class AuthManager:
    KEY_TTL = 30 * 60

    def __init__(self):
        self._keys: dict[str, float] = {}

    def login(self, username: str, password: str) -> str | None:
        if username != Config.DEFAULT_USERNAME or password != Config.DEFAULT_PASSWORD:
            return None
        key = str(uuid.uuid4())
        self._keys[key] = time.time() + self.KEY_TTL
        return key

    def is_valid(self, key: str) -> bool:
        expires_at = self._keys.get(key, 0)
        if expires_at <= time.time():
            self._keys.pop(key, None)
            return False
        return True


_auth = AuthManager()


def get_auth_manager() -> AuthManager:
    return _auth


def require_auth(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        bearer = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        key = bearer or request.headers.get("X-API-Key", "").strip()
        if not get_auth_manager().is_valid(key):
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
