"""Minimal Intent Hub HTTP API."""

from functools import wraps

from flask import Flask, jsonify, request
from flask_compress import Compress
from pydantic import ValidationError

from intent_hub.auth import get_auth_manager, require_auth
from intent_hub.config import Config
from intent_hub.core.components import get_component_manager
from intent_hub.models import LoginRequest, RouteRequest, ThresholdRequest
from intent_hub.services.prediction_service import PredictionService
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


@app.post("/auth/login")
@api_errors
def login():
    payload = LoginRequest(**(request.get_json() or {}))
    key = get_auth_manager().login(payload.username, payload.password)
    if not key:
        return jsonify({"error": "用户名或密码错误"}), 401
    return jsonify({"api_key": key})


@app.get("/agents")
@require_auth
def agents():
    store = get_component_manager().agent_store
    return jsonify([agent.model_dump() for agent in store.all()])


@app.patch("/agents/<int:agent_id>/thresholds")
@require_auth
@api_errors
def update_agent_thresholds(agent_id: int):
    payload = ThresholdRequest(**(request.get_json() or {}))
    agent = SyncService(get_component_manager()).update_thresholds(
        agent_id, payload.score_threshold, payload.negative_threshold
    )
    return jsonify(agent.model_dump())


@app.post("/sync")
@require_auth
@api_errors
def sync():
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
    return jsonify({"QDRANT_COLLECTION": Config.QDRANT_COLLECTION})


@app.post("/settings")
@require_auth
@api_errors
def update_settings():
    collection = str((request.get_json() or {}).get("QDRANT_COLLECTION", ""))
    Config.save_collection(collection)
    get_component_manager().reset_qdrant()
    return jsonify({"QDRANT_COLLECTION": Config.QDRANT_COLLECTION})


def init_app():
    return app
