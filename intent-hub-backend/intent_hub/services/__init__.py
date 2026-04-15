"""Service layer exports."""

from importlib import import_module

_EXPORTS = {
    "DiagnosticService": ("intent_hub.services.diagnostic_service", "DiagnosticService"),
    "ImportService": ("intent_hub.services.import_service", "ImportService"),
    "PredictionService": ("intent_hub.services.prediction_service", "PredictionService"),
    "RouteService": ("intent_hub.services.route_service", "RouteService"),
    "SkillScanService": ("intent_hub.services.skill_scan_service", "SkillScanService"),
    "SyncService": ("intent_hub.services.sync_service", "SyncService"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'intent_hub.services' has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
