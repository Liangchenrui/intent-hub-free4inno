"""Intent Hub package exports."""

from importlib import import_module

__version__ = "0.1.0"

_EXPORTS = {
    "Config": ("intent_hub.config", "Config"),
    "RouteConfig": ("intent_hub.models", "RouteConfig"),
    "PredictRequest": ("intent_hub.models", "PredictRequest"),
    "PredictResponse": ("intent_hub.models", "PredictResponse"),
    "ErrorResponse": ("intent_hub.models", "ErrorResponse"),
    "LoginRequest": ("intent_hub.models", "LoginRequest"),
    "LoginResponse": ("intent_hub.models", "LoginResponse"),
    "QwenEmbeddingEncoder": ("intent_hub.encoder", "QwenEmbeddingEncoder"),
    "IntentHubQdrantClient": ("intent_hub.qdrant_wrapper", "IntentHubQdrantClient"),
    "RouteManager": ("intent_hub.route_manager", "RouteManager"),
    "get_auth_manager": ("intent_hub.auth", "get_auth_manager"),
    "require_auth": ("intent_hub.auth", "require_auth"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'intent_hub' has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
