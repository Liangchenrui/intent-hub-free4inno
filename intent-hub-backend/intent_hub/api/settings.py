"""系统设置相关API"""

import requests
from flask import jsonify, request

from intent_hub.config import Config
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def get_settings():
    """获取系统配置项"""
    return jsonify(Config.to_dict()), 200


@handle_errors
def list_qdrant_collections():
    """List collections from the configured Qdrant endpoint without initializing components."""
    url = f"{Config.QDRANT_URL.rstrip('/')}/collections"
    headers = {"api-key": Config.QDRANT_API_KEY} if Config.QDRANT_API_KEY else {}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    payload = response.json()
    collections = payload.get("result", {}).get("collections", [])
    names = sorted(
        item.get("name") for item in collections if isinstance(item, dict) and item.get("name")
    )
    return jsonify({"items": names}), 200


@handle_errors
def update_settings():
    """更新系统配置项"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    try:
        Config.save(data)
        # 配置保存应立即返回；依赖组件在下次实际使用时按新配置懒加载。
        from intent_hub.core.components import get_component_manager

        component_manager = get_component_manager()
        component_manager.reset_components()
        index_settings = {
            "QDRANT_URL",
            "QDRANT_COLLECTION",
            "QDRANT_API_KEY",
            "EMBEDDING_SERVICE_URL",
            "EMBEDDING_MODEL_NAME",
        }
        if index_settings.intersection(data):
            from intent_hub.services.sync_task_service import get_sync_task_service

            route_ids = [route.id for route in component_manager.route_manager.get_all_routes()]
            if route_ids:
                for route_id in route_ids:
                    route = component_manager.route_manager.get_route(route_id)
                    current_version = route.sync.version if route and route.sync else 0
                    component_manager.route_manager.update_sync_state(
                        route_id,
                        status="pending",
                        version=current_version + 1,
                        error=None,
                    )
                get_sync_task_service(component_manager).enqueue_routes(route_ids)
        return jsonify(
            {"message": "配置更新成功，组件已重新加载", "settings": Config.to_dict()}
        ), 200
    except Exception as e:
        return jsonify({"error": "配置保存失败", "detail": str(e)}), 500


@handle_errors
def import_routes_from_qdrant():
    """Rebuild the local intent list from payloads in a selected collection."""
    data = request.get_json(silent=True) or {}
    collection = str(data.get("collection") or "").strip()
    if not collection:
        return jsonify({"error": "请求参数错误", "detail": "collection 不能为空"}), 400

    from intent_hub.core.components import get_component_manager
    from intent_hub.services.qdrant_import_service import QdrantImportService
    from intent_hub.services.sync_service import SyncService
    from intent_hub.services.sync_task_service import get_sync_task_service

    with SyncService.execution_lock:
        Config.save({"QDRANT_COLLECTION": collection})
        component_manager = get_component_manager()
        component_manager.reset_components()
        task_service = get_sync_task_service(component_manager)
        task_service.supersede_queued("Superseded by Qdrant collection recovery")
        service = QdrantImportService(component_manager.route_manager)
        routes = service.import_collection(collection)
    return jsonify(
        {
            "message": f"已从 Collection {collection} 恢复 {len(routes)} 个意图实体",
            "collection": collection,
            "routes_count": len(routes),
        }
    ), 200
