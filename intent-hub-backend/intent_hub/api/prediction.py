"""Single public routing API."""
from flask import g, jsonify, request
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from intent_hub.auth import extract_api_key, get_auth_manager
from intent_hub.config import Config
from intent_hub.core.components import get_component_manager, RoutingNotReady
from intent_hub.models import RouteRequest, PredictRequest
from intent_hub.services.prediction_service import PredictionService
from intent_hub.utils.logger import logger
import hmac


def error_response(code, message, status, detail=None):
    return jsonify({"success": False, "data": None, "error": {
        "code": code, "message": message, "detail": detail}}), status


def predict():
    key = extract_api_key()
    expected = Config.ROUTE_API_KEY or Config.AUTH_CODE
    authenticated = bool(key and expected and hmac.compare_digest(key, expected))
    if not authenticated and Config.AUTH_ENABLED and key:
        authenticated = get_auth_manager().is_valid(key)
    if not authenticated:
        return error_response("UNAUTHORIZED", "Authentication failed", 401)
    try:
        body = request.get_json()
        if not isinstance(body, dict):
            raise ValueError("请求体必须是 JSON 对象")
        payload = RouteRequest(**body)
        g.route_input = payload.query
        manager = get_component_manager()
        if hasattr(manager, "ready_snapshot"):
            manager = manager.ready_snapshot()
        results = PredictionService(manager).predict(PredictRequest(
            text=payload.query.strip(), collection=payload.collection,
            upstream_id=payload.upstream_id,
            learn_from_fallback=payload.learn_from_fallback))
        matched = [r for r in results if r.match_source != "default"]
        agents = []
        for result in matched:
            route = manager.route_manager.get_route(result.id)
            agents.append({"id": result.id, "name": result.name,
                           "route_key": result.route_key, "score": result.score,
                           "agent": route.details if route else {}})
        return jsonify({"success": True, "error": None, "data": {
            "matched": bool(matched), "agents": agents,
            "text": None if matched else Config.DEFAULT_ROUTE_TEXT,
            "match_source": results[0].match_source,
            "fallback_status": results[0].fallback_status}})
    except (ValidationError, ValueError, BadRequest, UnsupportedMediaType) as exc:
        return error_response("INVALID_REQUEST", "请求参数错误", 400, str(exc))
    except RoutingNotReady:
        return error_response("SERVICE_NOT_READY", "路由组件尚未就绪，请稍后重试", 503)
    except Exception:
        logger.exception("Routing request failed")
        return error_response("INTERNAL_ERROR", "服务异常", 500)
