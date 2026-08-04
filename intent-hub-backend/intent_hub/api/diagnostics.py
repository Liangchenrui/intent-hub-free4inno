from flask import jsonify, request
from intent_hub.core.components import get_component_manager
from intent_hub.services.diagnostic_service import DiagnosticService
from intent_hub.utils.error_handler import handle_errors
from intent_hub.models import RepairRequest, ApplyRepairRequest
from intent_hub.services.sync_task_service import get_sync_task_service

@handle_errors
def analyze_overlap(route_id):
    """分析指定路由与其他路由的重叠情况"""
    # 单路由详情接口默认不限制冲突数量，或者由前端参数指定
    max_conflicts = request.args.get("max_conflicts", type=int)
    
    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    
    result = diagnostic_service.analyze_route_overlap(route_id, max_conflicts=max_conflicts)
    return jsonify(result.dict()), 200

@handle_errors
def analyze_all_overlaps():
    """全局分析所有路由的重叠情况"""
    refresh = request.args.get("refresh", "false").lower() == "true"
    # 全局列表接口默认限制每个路由对返回的冲突点数量，以减小响应体积
    max_conflicts = request.args.get("max_conflicts", 10, type=int)
    
    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    
    if refresh:
        # 手动点击深度体检：现在改为同步执行，直接返回最新结果
        results = diagnostic_service.analyze_all_overlaps(use_cache=False, max_conflicts_per_pair=max_conflicts)
        return jsonify([r.dict() for r in results]), 200

    results = diagnostic_service.analyze_all_overlaps(use_cache=True, max_conflicts_per_pair=max_conflicts)
    return jsonify([r.dict() for r in results]), 200


@handle_errors
def umap_points():
    """返回用于可视化的 UMAP 2D 点云"""
    n_neighbors = request.args.get("n_neighbors", 15, type=int)
    min_dist = request.args.get("min_dist", 0.1, type=float)
    seed = request.args.get("seed", 42, type=int)

    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)

    data = diagnostic_service.build_umap_projection(
        n_neighbors=n_neighbors, min_dist=min_dist, seed=seed
    )
    return jsonify(data), 200


@handle_errors
def get_repair_suggestions():
    """获取 LLM 修复建议"""
    data = RepairRequest(**request.json)

    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)

    suggestion = diagnostic_service.get_repair_suggestions(
        data.source_route_id, data.target_route_id, language=data.language
    )
    return jsonify(suggestion.dict()), 200


@handle_errors
def apply_repair():
    """应用修复建议"""
    data = ApplyRepairRequest(**request.json)

    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)

    success = diagnostic_service.apply_repair(data.route_id, data.utterances)
    if success:
        get_sync_task_service(component_manager).enqueue_routes([data.route_id])
    return jsonify({"success": success}), 200
