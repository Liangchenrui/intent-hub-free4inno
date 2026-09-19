"""系统设置相关API"""

from flask import jsonify, request

from intent_hub.config import Config
from intent_hub.utils.error_handler import handle_errors
from intent_hub.services.collection_service import CollectionService


@handle_errors
def get_settings():
    """获取系统配置项"""
    return jsonify(Config.to_dict()), 200


@handle_errors
def list_qdrant_collections():
    """List collections from the configured Qdrant endpoint without initializing components."""
    return jsonify(CollectionService().list_collections()), 200


@handle_errors
def create_qdrant_collection():
    name = str((request.get_json(silent=True) or {}).get("name") or "")
    from intent_hub.core.components import get_component_manager

    result = CollectionService(get_component_manager()).create_collection(name)
    return jsonify(result), 201


@handle_errors
def update_settings():
    with Config.LOCK:
        return _update_settings()


def _update_settings():
    """更新系统配置项"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    try:
        before = Config.to_dict()
        Config.save(data)
        after = Config.to_dict()
        changed = {key for key in after if before.get(key) != after[key]}
        # 配置保存立即返回；新组件在后台预热。
        from intent_hub.core.components import get_component_manager

        component_manager = get_component_manager()
        component_settings = {
            "QDRANT_URL",
            "QDRANT_COLLECTION",
            "QDRANT_API_KEY",
            "EMBEDDING_SERVICE_URL",
            "EMBEDDING_MODEL_NAME",
            "EMBEDDING_API_FORMAT",
            "BATCH_SIZE", "QDRANT_WRITE_BATCH_SIZE", "QDRANT_TIMEOUT_SECONDS", "SERVICE_HTTP_TRUST_ENV",
        }
        if changed & {"LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL",
                      "LLM_FALLBACK_TIMEOUT_SECONDS", "LLM_FALLBACK_ENABLED"}:
            from threading import Thread
            from intent_hub.services.llm_runtime import warm_llm
            Thread(target=warm_llm, name='llm-warmup', daemon=True).start()
        if changed & component_settings:
            component_manager.reset_components()
        if changed & {"QDRANT_URL", "QDRANT_COLLECTION", "EMBEDDING_MODEL_NAME",
                      "EMBEDDING_SERVICE_URL", "EMBEDDING_API_FORMAT"}:
            from intent_hub.services.sync_task_service import get_sync_task_service

            get_sync_task_service(component_manager).enqueue_incremental_reindex()
        return jsonify(
            {"message": "配置更新成功" if changed else "配置未变化", "settings": after}
        ), 200
    except ValueError as e:
        return jsonify({"error": "配置参数错误", "detail": str(e)}), 400
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
