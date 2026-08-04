"""API module exports."""

from importlib import import_module

_EXPORTS = {
    "auth": ("intent_hub.api.auth", None),
    "prediction": ("intent_hub.api.prediction", None),
    "routes": ("intent_hub.api.routes", None),
    "reindex": ("intent_hub.api.reindex", None),
    "settings": ("intent_hub.api.settings", None),
    "diagnostics": ("intent_hub.api.diagnostics", None),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'intent_hub.api' has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    return value
