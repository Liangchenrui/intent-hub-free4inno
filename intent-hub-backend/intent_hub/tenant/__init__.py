"""Tenant-scoped runtime helpers."""

from importlib import import_module

_EXPORTS = {
    "TenantContext": ("intent_hub.tenant.context", "TenantContext"),
    "TenantComponentManager": ("intent_hub.tenant.components", "TenantComponentManager"),
    "TenantComponentRegistry": ("intent_hub.tenant.components", "TenantComponentRegistry"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'intent_hub.tenant' has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
