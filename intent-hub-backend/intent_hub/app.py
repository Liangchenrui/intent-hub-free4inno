"""Minimal Intent Hub HTTP API."""

from functools import wraps

from flask import Flask, jsonify, request
from flask_compress import Compress
from pydantic import ValidationError

from intent_hub.agent_compare import comparison_detail, comparison_summary
from intent_hub.auth import require_auth
from intent_hub.config import Config
from intent_hub.core.components import get_component_manager
from intent_hub.models import (
    AgentCreate, AgentUpdate, ApplyRepairRequest, MergeAgentsRequest,
    CollectionRequest, RecommendationRequest, RepairRequest, RouteRequest,
    ThresholdRequest,
)
from intent_hub.services.collection_service import CollectionService
from intent_hub.services.diagnostic_service import DiagnosticService
from intent_hub.services.health_service import check_external_services
from intent_hub.services.llm_service import LLMService
from intent_hub.services.prediction_service import PredictionService
from intent_hub.services.pull_service import PullService
from intent_hub.services.sync_service import SyncService
from intent_hub.utils.logger import logger


app = Flask(__name__)
Compress(app)


def api_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ValidationError as error:
            return jsonify({
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "请求参数错误",
                    "detail": str(error),
                },
            }), 400
        except ValueError as error:
            return jsonify({
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "请求参数错误",
                    "detail": str(error),
                },
            }), 400
        except Exception as error:
            logger.exception("API request failed: %s", request.path)
            return jsonify({
                "success": False,
                "data": None,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务异常",
                    "detail": str(error),
                },
            }), 500

    return wrapped


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/health/services")
def external_services_health():
    return jsonify(check_external_services())


@app.get("/agents")
@require_auth
def agents():
    store = get_component_manager().agent_store
    result = []
    for agent in store.all():
        item = agent.model_dump()
        item["comparison"] = comparison_summary(agent)
        result.append(item)
    return jsonify(result)


@app.get("/agents/<int:agent_id>/diff")
@require_auth
@api_errors
def agent_diff(agent_id: int):
    store = get_component_manager().agent_store
    agent = store.get(agent_id)
    if agent is None:
        raise ValueError("Agent 不存在")
    return jsonify(comparison_detail(agent, store.get_metadata("last_pull_at")))


@app.post("/agents")
@require_auth
@api_errors
def create_agent():
    payload = AgentCreate(**(request.get_json() or {}))
    agent = get_component_manager().agent_store.create_local(**payload.model_dump())
    return jsonify(agent.model_dump()), 201


@app.patch("/agents/<int:agent_id>")
@require_auth
@api_errors
def update_agent(agent_id: int):
    payload = AgentUpdate(**(request.get_json() or {}))
    agent = get_component_manager().agent_store.update(agent_id, payload.model_dump(exclude_none=True))
    return jsonify(agent.model_dump())


@app.delete("/agents/<int:agent_id>")
@require_auth
@api_errors
def delete_agent(agent_id: int):
    agent = get_component_manager().agent_store.update(agent_id, {"lifecycle_status": "deleted"})
    return jsonify(agent.model_dump())


@app.post("/agents/<int:agent_id>/restore-fields")
@require_auth
@api_errors
def restore_agent_fields(agent_id: int):
    fields = list((request.get_json() or {}).get("fields") or [])
    return jsonify(get_component_manager().agent_store.restore_fields(agent_id, fields).model_dump())


@app.post("/agents/<int:agent_id>/recommendations")
@require_auth
@api_errors
def recommend_agent_corpus(agent_id: int):
    agent = get_component_manager().agent_store.get(agent_id)
    if not agent:
        raise ValueError("Agent 不存在")
    payload = RecommendationRequest(**(request.get_json() or {}))
    return jsonify({"items": LLMService().recommendations(agent, payload), "polarity": payload.polarity})


@app.patch("/agents/<int:agent_id>/thresholds")
@require_auth
@api_errors
def update_agent_thresholds(agent_id: int):
    payload = ThresholdRequest(**(request.get_json() or {}))
    agent = get_component_manager().agent_store.update(agent_id, {
        "score_threshold": payload.score_threshold, "negative_threshold": payload.negative_threshold,
    })
    return jsonify(agent.model_dump())


@app.post("/agents/pull")
@require_auth
@api_errors
def pull_agents():
    return jsonify(PullService(get_component_manager()).pull())


@app.post("/vectors/sync")
@require_auth
@api_errors
def sync_vectors():
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "incremental"))
    agent_ids = payload.get("agent_ids")
    return jsonify(SyncService(get_component_manager()).sync(mode=mode, agent_ids=agent_ids))


@app.post("/sync")
@require_auth
@api_errors
def sync():
    """Deprecated compatibility alias: sync local SQLite data to Qdrant only."""
    mode = str((request.get_json(silent=True) or {}).get("mode", "incremental"))
    return jsonify(SyncService(get_component_manager()).sync(mode=mode))


@app.get("/sync/status")
@require_auth
@api_errors
def sync_status():
    return jsonify(SyncService(get_component_manager()).status())


@app.post("/route")
@require_auth
@api_errors
def route():
    payload = RouteRequest(**(request.get_json() or {}))
    query = payload.query.strip()
    if not query:
        raise ValueError("query 不能为空")
    return jsonify({
        "success": True,
        "data": PredictionService(get_component_manager()).route(query),
        "error": None,
    })


@app.get("/settings")
@require_auth
def settings():
    return jsonify(Config.to_dict())


@app.post("/settings")
@require_auth
@api_errors
def update_settings():
    Config.save(request.get_json() or {})
    get_component_manager().reinit_components()
    return jsonify({"message": "配置已保存，运行组件将在下次请求时重新连接", "settings": Config.to_dict()})


@app.get("/collections")
@require_auth
@api_errors
def collections():
    return jsonify(CollectionService(get_component_manager()).list_collections())


@app.post("/collections")
@require_auth
@api_errors
def create_collection():
    payload = CollectionRequest(**(request.get_json() or {}))
    result = CollectionService(get_component_manager()).create_collection(payload.name)
    return jsonify(result), 201


@app.post("/collections/restore")
@require_auth
@api_errors
def restore_collection():
    payload = CollectionRequest(**(request.get_json() or {}))
    result = CollectionService(get_component_manager()).restore_collection(payload.name)
    return jsonify(result)


@app.get("/diagnostics/overlap")
@require_auth
@api_errors
def diagnostics_overlap():
    refresh = request.args.get("refresh", "false").lower() == "true"
    limit = request.args.get("max_conflicts", 10, type=int)
    service = DiagnosticService(get_component_manager())
    return jsonify([item.model_dump() for item in service.analyze_all(refresh=refresh, max_conflicts=limit)])


@app.get("/diagnostics/overlap/<int:agent_id>")
@require_auth
@api_errors
def diagnostics_agent_overlap(agent_id: int):
    result = DiagnosticService(get_component_manager()).analyze_route(agent_id)
    return jsonify(result.model_dump())


@app.get("/diagnostics/umap")
@require_auth
@api_errors
def diagnostics_umap():
    return jsonify(DiagnosticService(get_component_manager()).umap_points(
        n_neighbors=request.args.get("n_neighbors", 15, type=int),
        min_dist=request.args.get("min_dist", 0.1, type=float),
        seed=request.args.get("seed", 42, type=int),
    ))


@app.post("/diagnostics/repair")
@require_auth
@api_errors
def diagnostics_repair():
    payload = RepairRequest(**(request.get_json() or {}))
    return jsonify(DiagnosticService(get_component_manager()).repair(payload.source_route_id, payload.target_route_id))


@app.post("/diagnostics/apply-repair")
@require_auth
@api_errors
def diagnostics_apply_repair():
    payload = ApplyRepairRequest(**(request.get_json() or {}))
    values = {"utterances": payload.utterances}
    if payload.negative_samples is not None:
        values["negative_samples"] = payload.negative_samples
    agent = get_component_manager().agent_store.update(payload.route_id, values)
    return jsonify(agent.model_dump())


@app.post("/diagnostics/merge")
@require_auth
@api_errors
def diagnostics_merge():
    payload = MergeAgentsRequest(**(request.get_json() or {}))
    agent = DiagnosticService(get_component_manager()).merge(payload.source_agent_id, payload.target_agent_id, payload.title, payload.text)
    return jsonify(agent.model_dump()), 201


def init_app():
    return app
