"""Optional upstream Agent synchronization endpoints."""

from flask import jsonify, request

from intent_hub.core.components import get_component_manager
from intent_hub.route_compare import comparison_detail
from intent_hub.services.sync_task_service import get_sync_task_service
from intent_hub.services.upstream_agent_service import UpstreamAgentService
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def pull_agents():
    result = UpstreamAgentService(get_component_manager()).pull()
    result.pop("affected_route_ids", None)
    return jsonify(result), 200


@handle_errors
def route_diff(route_id: int):
    route = get_component_manager().route_manager.get_route(route_id)
    if route is None:
        return jsonify({"error": "路由不存在", "detail": f"路由 {route_id} 不存在"}), 404
    if route.source is None or route.source.type != "upstream_agent":
        return jsonify({"error": "请求参数错误", "detail": "该路由不是上游 Agent"}), 400
    return jsonify(comparison_detail(route)), 200


@handle_errors
def restore_fields(route_id: int):
    fields = (request.get_json(silent=True) or {}).get("fields", [])
    if not isinstance(fields, list):
        return jsonify({"error": "请求参数错误", "detail": "fields 必须是数组"}), 400
    manager = get_component_manager()
    route = UpstreamAgentService(manager).restore_fields(route_id, fields)
    get_sync_task_service(manager).enqueue_routes([route.id])
    return jsonify(route.model_dump()), 200
