"""重新索引相关API"""

from flask import jsonify, request

from intent_hub.core.components import get_component_manager
from intent_hub.services.sync_service import SyncService
from intent_hub.services.sync_task_service import get_sync_task_service
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def reindex():
    """增量重新索引：只更新变化的路由

    支持可选参数：
    - force_full: 如果为true，则执行全量重建（清空后重新创建）
    """
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    # 获取请求参数
    data = request.get_json() or {}
    force_full = data.get("force_full", False)

    sync_service = SyncService(component_manager)
    with SyncService.execution_lock:
        result = sync_service.reindex(force_full=force_full)

    return jsonify(result), 200


@handle_errors
def sync_route():
    """同步单个路由到向量数据库
    
    支持同步单个或多个路由：
    - route_id: 单个路由ID（整数）
    - route_ids: 多个路由ID列表（数组）
    """
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    # 获取请求参数
    data = request.get_json() or {}
    
    sync_service = SyncService(component_manager)
    
    # 支持单个路由ID或多个路由ID列表
    if "route_ids" in data:
        route_ids = data["route_ids"]
        if not isinstance(route_ids, list):
            return jsonify({"error": "route_ids 必须是数组"}), 400
        with SyncService.execution_lock:
            result = sync_service.sync_routes(route_ids)
    elif "route_id" in data:
        route_id = data["route_id"]
        if not isinstance(route_id, int):
            return jsonify({"error": "route_id 必须是整数"}), 400
        with SyncService.execution_lock:
            result = sync_service.sync_route(route_id)
    else:
        return jsonify({"error": "必须提供 route_id 或 route_ids 参数"}), 400

    return jsonify(result), 200


@handle_errors
def list_sync_tasks():
    active_only = request.args.get("active", "false").lower() == "true"
    service = get_sync_task_service(get_component_manager())
    return jsonify(service.list_tasks(active_only=active_only)), 200


@handle_errors
def retry_sync_task(task_id: str):
    service = get_sync_task_service(get_component_manager())
    return jsonify(service.retry(task_id)), 200
