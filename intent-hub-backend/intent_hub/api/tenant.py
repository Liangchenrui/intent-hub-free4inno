"""Tenant-scoped runtime and control-plane APIs."""

import json
from pathlib import Path

from flask import g, jsonify, request
from pydantic import BaseModel, Field, ValidationError

from intent_hub.auth import require_tenant_access
from intent_hub.config import Config
from intent_hub.models import PredictRequest, RepairRequest, ApplyRepairRequest, RouteConfig, RouteImportDraft
from intent_hub.platform.registry import TenantRegistry
from intent_hub.tenant.components import TenantComponentRegistry
from intent_hub.utils.error_handler import handle_errors, validate_request


_tenant_component_registry: TenantComponentRegistry | None = None


def get_tenant_component_registry() -> TenantComponentRegistry:
    global _tenant_component_registry
    if _tenant_component_registry is None:
        _tenant_component_registry = TenantComponentRegistry()
    return _tenant_component_registry


_tenant_registry: TenantRegistry | None = None


def get_tenant_registry() -> TenantRegistry:
    global _tenant_registry
    if _tenant_registry is None:
        _tenant_registry = TenantRegistry(Config.PLATFORM_DATA_DIR / "tenants.json")
    return _tenant_registry


def build_skill_draft_generator(component_manager):
    from intent_hub.services.route_service import RouteService

    route_service = RouteService(component_manager)

    def generator(skill_file: Path, content: str) -> dict:
        draft = route_service.generate_route_from_skill(type("Req", (), {"skill_content": content})())
        return draft.model_dump() if hasattr(draft, "model_dump") else draft.dict()

    return generator


def build_skill_draft_applier(component_manager):
    from intent_hub.services.import_service import ImportService

    import_service = ImportService(component_manager)
    route_manager = component_manager.route_manager

    def applier(draft_payload: dict, source, skill_file: Path) -> dict:
        draft = RouteImportDraft.model_validate(draft_payload)
        result = import_service.import_routes(
            routes=[RouteConfig.model_validate(route.model_dump()) for route in draft.routes],
            mode=draft.mode,
            import_origin="skill_scan",
        )
        route_key = draft.routes[0].route_key if draft.routes else ""
        route = route_manager.get_route_by_key(route_key) if route_key else None
        return {"result": result, "route_id": route.id if route else None}

    return applier


def _tenant_component_manager():
    return get_tenant_component_registry().get(g.tenant_context)


def _filter_settings_payload(payload: dict) -> dict:
    allowlist = {
        "EMBEDDING_SERVICE_URL",
        "EMBEDDING_MODEL_NAME",
        "EMBEDDING_DEVICE",
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "UTTERANCE_GENERATION_PROMPT",
        "AGENT_REPAIR_PROMPT",
        "SKILL_ROUTE_IMPORT_PROMPT",
        "REGION_THRESHOLD_SIGNIFICANT",
        "INSTANCE_THRESHOLD_AMBIGUOUS",
        "BATCH_SIZE",
    }
    return {key: value for key, value in payload.items() if key in allowlist}


def _load_tenant_settings() -> dict:
    settings_path = g.tenant_context.settings_path
    defaults = _filter_settings_payload(Config.to_dict())
    if not settings_path.exists():
        return defaults
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return defaults
    filtered = _filter_settings_payload(payload)
    merged = dict(defaults)
    merged.update(filtered)
    return merged


def _save_tenant_settings(payload: dict) -> dict:
    settings_path = g.tenant_context.settings_path
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    current = _load_tenant_settings()
    current.update(_filter_settings_payload(payload))
    settings_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return current


@handle_errors
@require_tenant_access
def me():
    return jsonify(
        {
            "tenant_id": g.tenant_context.tenant_id,
            "tenant_name": g.tenant_context.tenant_name,
            "code_id": g.current_access_code.code_id,
            "code_label": g.current_access_code.label,
            "collection": g.tenant_context.collection_name,
        }
    ), 200


@handle_errors
@require_tenant_access
@validate_request(PredictRequest)
def route(predict_req: PredictRequest):
    from intent_hub.services.prediction_service import PredictionService

    component_manager = _tenant_component_manager()
    prediction_service = PredictionService(component_manager)
    matches = prediction_service.predict(predict_req)

    top_match = matches[0]
    return jsonify(
        {
            "tenant_id": g.tenant_context.tenant_id,
            "route_key": top_match.route_key,
            "score": top_match.score,
            "matches": [
                m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in matches
            ],
            "collection": g.tenant_context.collection_name,
        }
    ), 200


@handle_errors
@require_tenant_access
@validate_request(PredictRequest)
def dispatch(predict_req: PredictRequest):
    from intent_hub.services.prediction_service import PredictionService

    component_manager = _tenant_component_manager()
    prediction_service = PredictionService(component_manager)
    matches = prediction_service.predict(predict_req)

    top_match = matches[0]
    return jsonify(
        {
            "tenant_id": g.tenant_context.tenant_id,
            "route_key": top_match.route_key,
            "score": top_match.score,
            "matches": [
                m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in matches
            ],
            "collection": g.tenant_context.collection_name,
            "dispatch": {
                "status": "not_executed",
                "executor": "none",
                "suggestion": {
                    "type": "route_key",
                    "route_key": top_match.route_key,
                    "confidence": top_match.score,
                },
            },
        }
    ), 200


@handle_errors
@require_tenant_access
def get_settings():
    return jsonify(_load_tenant_settings()), 200


@handle_errors
@require_tenant_access
def update_settings():
    data = request.get_json() or {}
    payload = _filter_settings_payload(data)
    if not payload:
        return jsonify({"error": "请求体不能为空"}), 400
    try:
        updated = _save_tenant_settings(payload)
        get_tenant_component_registry().clear(g.tenant_context.tenant_id)
        return jsonify({"message": "配置更新成功", "settings": updated}), 200
    except Exception as e:
        return jsonify({"error": "配置保存失败", "detail": str(e)}), 500


@handle_errors
@require_tenant_access
def list_skill_sources():
    tenant = get_tenant_registry().get_tenant(g.tenant_context.tenant_id)
    items = [] if tenant is None else [source.model_dump(mode="json") for source in tenant.skill_sources]
    return jsonify({"items": items}), 200


@handle_errors
@require_tenant_access
def create_skill_source():
    data = request.get_json() or {}
    _, source = get_tenant_registry().create_skill_source(
        tenant_id=g.tenant_context.tenant_id,
        path=data.get("path", ""),
        sync_mode=data.get("sync_mode", "draft"),
        enabled=data.get("enabled", True),
    )
    return jsonify({"item": source.model_dump(mode="json")}), 201


@handle_errors
@require_tenant_access
def scan_skill_sources():
    from intent_hub.services.skill_scan_service import SkillScanService

    tenant = get_tenant_registry().get_tenant(g.tenant_context.tenant_id)
    if tenant is None:
        raise ValueError(f"Tenant not found: {g.tenant_context.tenant_id}")
    component_manager = get_tenant_component_registry().get(g.tenant_context)
    scan_service = SkillScanService(
        g.tenant_context,
        draft_generator=build_skill_draft_generator(component_manager),
        draft_applier=build_skill_draft_applier(component_manager),
    )
    result = scan_service.scan_sources(tenant.skill_sources)
    return jsonify(result), 200


@handle_errors
@require_tenant_access
def list_skill_drafts():
    path = g.tenant_context.skills_index_path
    if not path.exists():
        return jsonify({"items": []}), 200
    payload = json.loads(path.read_text(encoding="utf-8"))
    return jsonify({"items": payload.get("items", [])}), 200


@handle_errors
@require_tenant_access
def apply_skill_draft():
    from intent_hub.services.import_service import ImportService

    data = request.get_json() or {}
    draft_file = (data.get("draft_file", "") or "").strip()
    if not draft_file:
        raise ValueError("draft_file is required")

    draft_path = Path(draft_file).resolve()
    imports_root = g.tenant_context.imports_dir.resolve()
    if imports_root not in draft_path.parents:
        raise ValueError("draft_file must be inside tenant imports dir")
    if not draft_path.exists():
        raise ValueError("draft_file not found")

    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    draft = RouteImportDraft.model_validate(payload)
    component_manager = get_tenant_component_registry().get(g.tenant_context)
    import_service = ImportService(component_manager)
    result = import_service.import_routes(
        routes=[RouteConfig.model_validate(route.model_dump()) for route in draft.routes],
        mode=draft.mode,
        import_origin="skill_scan",
    )
    return jsonify(result), 200


@handle_errors
@require_tenant_access
def list_routes():
    from intent_hub.services.route_service import RouteService

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    routes = route_service.get_all_routes()
    return jsonify([route.dict() for route in routes]), 200


@handle_errors
@require_tenant_access
def search_routes():
    from intent_hub.services.route_service import RouteService

    query = request.args.get("q", "").strip()
    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    routes = route_service.search_routes(query)
    return jsonify([route.dict() for route in routes]), 200


@handle_errors
@require_tenant_access
@validate_request(RouteConfig)
def create_route(route: RouteConfig):
    from intent_hub.services.route_service import RouteService

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    created_route = route_service.create_route(route)
    return jsonify(created_route.dict()), 201


@handle_errors
@require_tenant_access
def update_route(route_id: int):
    from intent_hub.services.route_service import RouteService

    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    try:
        route = RouteConfig(**data)
    except ValidationError as e:
        return jsonify({"error": "请求参数错误", "detail": str(e)}), 400
    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    updated_route = route_service.update_route(route_id, route)
    return jsonify(updated_route.dict()), 200


@handle_errors
@require_tenant_access
def delete_route(route_id: int):
    from intent_hub.services.route_service import RouteService

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    route_service.delete_route(route_id)
    return jsonify({"message": f"路由 {route_id} 已删除"}), 200


@handle_errors
@require_tenant_access
def generate_utterances():
    from intent_hub.services.route_service import RouteService

    data = request.get_json() or {}
    try:
        req = PredictRequest.model_validate(data) if "text" in data else None
    except Exception:
        req = None
    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    # Reuse original request shape from routes.generate_utterances
    from intent_hub.models import GenerateUtterancesRequest

    req = GenerateUtterancesRequest(**data)
    updated_route = route_service.generate_utterances(req)
    return jsonify(updated_route.dict()), 200


@handle_errors
@require_tenant_access
def import_route_from_skill():
    from intent_hub.services.route_service import RouteService

    data = request.get_json() or {}
    from intent_hub.models import SkillRouteImportRequest

    req = SkillRouteImportRequest(**data)
    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_service = RouteService(component_manager)
    draft = route_service.generate_route_from_skill(req)
    return jsonify(draft.model_dump() if hasattr(draft, "model_dump") else draft.dict()), 200


class ImportRoutesRequest(BaseModel):
    routes: list[RouteConfig] = Field(..., description="要导入的路由列表")
    mode: str = Field(default="merge", description="导入模式：merge | replace")


@handle_errors
@require_tenant_access
def import_routes():
    from intent_hub.services.import_service import ImportService

    data = request.get_json() or {}
    try:
        req = ImportRoutesRequest(**data)
    except ValidationError as e:
        return jsonify({"error": "请求参数错误", "detail": str(e)}), 400

    mode = (req.mode or "merge").lower().strip()
    if mode not in ("merge", "replace"):
        return jsonify({"error": "请求参数错误", "detail": "mode 仅支持 'merge' 或 'replace'"}), 400

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    import_service = ImportService(component_manager)
    result = import_service.import_routes(
        routes=req.routes,
        mode=mode,
        import_origin="api_import",
    )
    return jsonify({"message": "导入成功", **result}), 200


class AddNegativeSamplesRequest(BaseModel):
    negative_samples: list[str] = Field(..., description="负例语句列表")
    negative_threshold: float = Field(default=0.95, ge=0.0, le=1.0)


@handle_errors
@require_tenant_access
def add_negative_samples(route_id: int):
    data = request.get_json() or {}
    try:
        req = AddNegativeSamplesRequest(**data)
    except ValidationError as e:
        return jsonify({"error": "请求参数错误", "detail": str(e)}), 400

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_manager = component_manager.route_manager
    route = route_manager.get_route(route_id)
    if not route:
        return jsonify({"error": "路由不存在", "detail": f"路由ID {route_id} 不存在"}), 404

    existing_negative_samples = getattr(route, "negative_samples", [])
    new_negative_samples = list(set(existing_negative_samples + req.negative_samples))
    route.negative_samples = new_negative_samples
    route.negative_threshold = req.negative_threshold
    route_manager.add_route(route)

    return jsonify(
        {
            "message": f"成功为路由 {route_id} 添加 {len(req.negative_samples)} 个负例样本",
            "route_id": route_id,
            "total_negative_samples": len(new_negative_samples),
        }
    ), 200


@handle_errors
@require_tenant_access
def delete_negative_samples(route_id: int):
    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    route_manager = component_manager.route_manager
    route = route_manager.get_route(route_id)
    if not route:
        return jsonify({"error": "路由不存在", "detail": f"路由ID {route_id} 不存在"}), 404
    route.negative_samples = []
    route_manager.add_route(route)
    return jsonify({"message": f"成功删除路由 {route_id} 的所有负例样本", "route_id": route_id}), 200


@handle_errors
@require_tenant_access
def reindex():
    from intent_hub.services.sync_service import SyncService

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    data = request.get_json() or {}
    force_full = data.get("force_full", False)
    sync_service = SyncService(component_manager)
    result = sync_service.reindex(force_full=force_full)
    return jsonify(result), 200


@handle_errors
@require_tenant_access
def sync_route():
    from intent_hub.services.sync_service import SyncService

    component_manager = _tenant_component_manager()
    component_manager.ensure_ready()
    data = request.get_json() or {}
    sync_service = SyncService(component_manager)
    if "route_ids" in data:
        route_ids = data["route_ids"]
        if not isinstance(route_ids, list):
            return jsonify({"error": "route_ids 必须是数组"}), 400
        result = sync_service.sync_routes(route_ids)
    elif "route_id" in data:
        route_id = data["route_id"]
        if not isinstance(route_id, int):
            return jsonify({"error": "route_id 必须是整数"}), 400
        result = sync_service.sync_route(route_id)
    else:
        return jsonify({"error": "必须提供 route_id 或 route_ids 参数"}), 400
    return jsonify(result), 200


@handle_errors
@require_tenant_access
def analyze_overlap(route_id: int):
    from intent_hub.services.diagnostic_service import DiagnosticService

    max_conflicts = request.args.get("max_conflicts", type=int)
    component_manager = _tenant_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    result = diagnostic_service.analyze_route_overlap(route_id, max_conflicts=max_conflicts)
    return jsonify(result.dict()), 200


@handle_errors
@require_tenant_access
def analyze_all_overlaps():
    from intent_hub.services.diagnostic_service import DiagnosticService

    refresh = request.args.get("refresh", "false").lower() == "true"
    max_conflicts = request.args.get("max_conflicts", 10, type=int)
    component_manager = _tenant_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    if refresh:
        results = diagnostic_service.analyze_all_overlaps(use_cache=False, max_conflicts_per_pair=max_conflicts)
        return jsonify([r.dict() for r in results]), 200
    results = diagnostic_service.analyze_all_overlaps(use_cache=True, max_conflicts_per_pair=max_conflicts)
    return jsonify([r.dict() for r in results]), 200


@handle_errors
@require_tenant_access
def umap_points():
    from intent_hub.services.diagnostic_service import DiagnosticService

    n_neighbors = request.args.get("n_neighbors", 15, type=int)
    min_dist = request.args.get("min_dist", 0.1, type=float)
    seed = request.args.get("seed", 42, type=int)
    component_manager = _tenant_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    data = diagnostic_service.build_umap_projection(n_neighbors=n_neighbors, min_dist=min_dist, seed=seed)
    return jsonify(data), 200


@handle_errors
@require_tenant_access
def get_repair_suggestions():
    from intent_hub.services.diagnostic_service import DiagnosticService

    data = RepairRequest(**request.json)
    component_manager = _tenant_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    suggestion = diagnostic_service.get_repair_suggestions(data.source_route_id, data.target_route_id)
    return jsonify(suggestion.dict()), 200


@handle_errors
@require_tenant_access
def apply_repair():
    from intent_hub.services.diagnostic_service import DiagnosticService

    data = ApplyRepairRequest(**request.json)
    component_manager = _tenant_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    success = diagnostic_service.apply_repair(data.route_id, data.utterances)
    return jsonify({"success": success}), 200
