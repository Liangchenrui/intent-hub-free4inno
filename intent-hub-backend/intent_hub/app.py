"""Flask application entry point."""

from flask import Flask
from flask_compress import Compress

from intent_hub.auth import require_auth
from intent_hub.core.components import get_component_manager

app = Flask(__name__)
Compress(app)

from intent_hub.services.log_service import install_request_logging, list_records

install_request_logging(app)


@app.get("/logs/<kind>")
def logs(kind):
    from flask import request
    from intent_hub.config import Config
    from intent_hub.compat_auth import require_auth as require_bupt_auth

    authenticate = (require_bupt_auth
                    if Config.API_COMPAT_PROFILE == "bupt" and not request.path.startswith('/compat/master/')
                    else require_auth)
    return authenticate(list_records)(kind)


@app.route("/health", methods=["GET"])
def health():
    """Process-level liveness probe."""
    return {"status": "ok"}, 200


@app.get("/health/ready")
def routing_readiness():
    manager = get_component_manager()
    manager.start_warmup()
    state = manager.readiness()
    return state, 200 if state['status'] == 'ready' else 503


@app.route("/health/services", methods=["GET"])
@require_auth
def service_health():
    """Probe the external services used by the router."""
    from intent_hub.api import health

    return health.get_service_health()


@app.route("/auth/login", methods=["POST"])
def login():
    """Login (no auth required)."""
    from intent_hub.api import auth

    return auth.login()


@app.route("/predict", methods=["POST"])
def predict():
    """Route prediction (Telestar auth)."""
    from intent_hub.api import prediction

    return prediction.predict()


@app.route("/routes", methods=["GET"])
@require_auth
def get_routes():
    """List all routes."""
    from intent_hub.api import routes

    return routes.get_routes()


@app.route("/routes/search", methods=["GET"])
@require_auth
def search_routes():
    """Search routes."""
    from intent_hub.api import routes

    return routes.search_routes()


@app.route("/routes/upstream-pull", methods=["POST"])
@require_auth
def pull_upstream_agents():
    """Refresh local routes from the configured read-only Agent API."""
    from intent_hub.api import upstream_agents

    return upstream_agents.pull_agents()


@app.route("/routes/<int:route_id>/upstream-diff", methods=["GET"])
@require_auth
def get_upstream_diff(route_id: int):
    from intent_hub.api import upstream_agents

    return upstream_agents.route_diff(route_id)


@app.route("/routes/<int:route_id>/restore-upstream-fields", methods=["POST"])
@require_auth
def restore_upstream_fields(route_id: int):
    from intent_hub.api import upstream_agents

    return upstream_agents.restore_fields(route_id)


@app.route("/routes", methods=["POST"])
@require_auth
def create_route():
    """Create route."""
    from intent_hub.api import routes

    return routes.create_route()


@app.route("/routes/<int:route_id>", methods=["PUT"])
@require_auth
def update_route(route_id: int):
    """Update route by ID."""
    from intent_hub.api import routes

    return routes.update_route(route_id)


@app.route("/routes/<int:route_id>", methods=["DELETE"])
@require_auth
def delete_route(route_id: int):
    """Delete route by ID."""
    from intent_hub.api import routes

    return routes.delete_route(route_id)


@app.route("/routes/generate-utterances", methods=["POST"])
@require_auth
def generate_utterances():
    """Generate utterances from Agent info."""
    from intent_hub.api import routes

    return routes.generate_utterances()


@app.route("/routes/import-skill", methods=["POST"])
@require_auth
def import_route_from_skill():
    """Generate route draft from SKILL.md content."""
    from intent_hub.api import routes

    return routes.import_route_from_skill()


@app.route("/routes/import", methods=["POST"])
@require_auth
def import_routes():
    """Import routes from JSON (merge/replace)."""
    from intent_hub.api import routes

    return routes.import_routes()


@app.route("/routes/<int:route_id>/negative-samples", methods=["POST"])
@require_auth
def add_negative_samples(route_id: int):
    """Add Negative Utterances for route."""
    from intent_hub.api import routes

    return routes.add_negative_samples(route_id)


@app.route("/routes/<int:route_id>/negative-samples", methods=["DELETE"])
@require_auth
def delete_negative_samples(route_id: int):
    """Delete all Negative Utterances for route."""
    from intent_hub.api import routes

    return routes.delete_negative_samples(route_id)


@app.route("/routes/<int:route_id>/feedback/positive", methods=["POST", "DELETE"])
@require_auth
def positive_feedback(route_id: int):
    from flask import request
    from intent_hub.api import routes

    return routes.add_positive_feedback(route_id) if request.method == "POST" else routes.delete_positive_feedback(route_id)


@app.route("/routes/<int:route_id>/feedback/negative", methods=["POST", "DELETE"])
@require_auth
def negative_feedback(route_id: int):
    from flask import request
    from intent_hub.api import routes

    return routes.add_negative_feedback(route_id) if request.method == "POST" else routes.delete_negative_feedback(route_id)


@app.route("/reindex", methods=["POST"])
@require_auth
def reindex_route():
    """Reindex."""
    from intent_hub.api import reindex

    return reindex.reindex()


@app.route("/reindex/sync-route", methods=["POST"])
@require_auth
def sync_route():
    """Sync one or more routes to vector DB."""
    from intent_hub.api import reindex

    return reindex.sync_route()


@app.route("/sync-tasks", methods=["GET"])
@require_auth
def list_sync_tasks():
    """List persistent background synchronization tasks."""
    from intent_hub.api import reindex

    return reindex.list_sync_tasks()


@app.route("/sync-tasks/<task_id>/retry", methods=["POST"])
@require_auth
def retry_sync_task(task_id: str):
    """Retry a failed background synchronization task."""
    from intent_hub.api import reindex

    return reindex.retry_sync_task(task_id)


@app.route("/diagnostics/overlap", methods=["GET"])
@require_auth
def analyze_all_overlaps():
    """Analyze overlap for all routes."""
    from intent_hub.api import diagnostics

    return diagnostics.analyze_all_overlaps()


@app.route("/diagnostics/overlap/<int:route_id>", methods=["GET"])
@require_auth
def analyze_overlap(route_id: int):
    """Analyze overlap for one route."""
    from intent_hub.api import diagnostics

    return diagnostics.analyze_overlap(route_id)


@app.route("/diagnostics/umap", methods=["GET"])
@require_auth
def diagnostics_umap():
    """UMAP point cloud data."""
    from intent_hub.api import diagnostics

    return diagnostics.umap_points()


@app.route("/diagnostics/repair", methods=["POST"])
@require_auth
def get_repair_suggestions():
    """Get LLM repair suggestions."""
    from intent_hub.api import diagnostics

    return diagnostics.get_repair_suggestions()


@app.route("/diagnostics/apply-repair", methods=["POST"])
@require_auth
def apply_repair():
    """Apply repair suggestions."""
    from intent_hub.api import diagnostics

    return diagnostics.apply_repair()


@app.route("/settings", methods=["GET"])
@require_auth
def get_settings():
    """Get system settings."""
    from intent_hub.api import settings

    return settings.get_settings()


@app.route("/settings/qdrant-collections", methods=["GET"])
@require_auth
def list_qdrant_collections():
    """List collections available at the configured Qdrant endpoint."""
    from intent_hub.api import settings

    return settings.list_qdrant_collections()


@app.route("/settings/qdrant-collections", methods=["POST"])
@require_auth
def create_qdrant_collection():
    """Create an empty collection using the active embedding dimensions."""
    from intent_hub.api import settings

    return settings.create_qdrant_collection()


@app.route("/settings/qdrant-import", methods=["POST"])
@require_auth
def import_routes_from_qdrant():
    """Replace local routes with intent payloads recovered from Qdrant."""
    from intent_hub.api import settings

    return settings.import_routes_from_qdrant()


@app.route("/settings", methods=["POST"])
@require_auth
def update_settings():
    """Update system settings."""
    from intent_hub.api import settings

    return settings.update_settings()


def init_app():
    """Initialize local storage and start remote work in the background."""
    component_manager = get_component_manager()
    component_manager.ensure_routes_ready()
    component_manager.start_warmup()
    from threading import Thread
    from intent_hub.services.llm_runtime import warm_llm
    Thread(target=warm_llm, name='llm-warmup', daemon=True).start()
    from intent_hub.services.sync_task_service import get_sync_task_service

    get_sync_task_service(component_manager)

    return app


@app.post('/routes/<int:route_id>/recommendations')
@require_auth
def recommend_samples(route_id):
    from flask import request, jsonify
    from intent_hub.compat_models import RecommendationRequest
    from intent_hub.services.llm_service import LLMService
    from intent_hub.utils.error_handler import handle_errors
    @handle_errors
    def invoke():
        components = get_component_manager()
        route = components.route_manager.get_route(route_id)
        if route is None:
            return jsonify({'error': 'Route not found'}), 404
        payload = RecommendationRequest(**(request.get_json() or {}))
        return jsonify({'items': LLMService().recommendations(components.agent_store.from_route(route), payload), 'polarity': payload.polarity})
    return invoke()


@app.post('/routes/merge')
@require_auth
def merge_routes():
    from flask import request, jsonify
    from intent_hub.compat_models import MergeAgentsRequest
    from intent_hub.utils.error_handler import handle_errors
    @handle_errors
    def invoke():
        components = get_component_manager()
        data = MergeAgentsRequest(**(request.get_json() or {}))
        source = components.route_manager.get_route(data.source_agent_id)
        target = components.route_manager.get_route(data.target_agent_id)
        if source is None or target is None:
            return jsonify({'error': 'Route not found'}), 404
        store = components.agent_store
        result = store.merge(store.from_route(source).id, store.from_route(target).id, data.title, data.text)
        from intent_hub.services.sync_task_service import get_sync_task_service
        merged_id = store.internal_id(result.id)
        get_sync_task_service(components).enqueue_routes([source.id, target.id, merged_id])
        return jsonify(components.route_manager.get_route(merged_id).model_dump()), 201
    return invoke()


def register_compatibility():
    from intent_hub.compat_api import app as bupt
    from intent_hub.config import Config
    import re
    original = list(app.url_map.iter_rules())
    for rule in original:
        if rule.endpoint == 'static':
            continue
        app.add_url_rule('/compat/master' + rule.rule, 'master_' + rule.endpoint,
                         app.view_functions[rule.endpoint], methods=rule.methods)
    app.register_blueprint(bupt, url_prefix='/compat/bupt')
    bupt_rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith('bupt.')]
    for rule in bupt_rules:
        path = rule.rule.removeprefix('/compat/bupt')
        methods = rule.methods - {'HEAD', 'OPTIONS'}
        collisions = [r for r in original if re.sub(r'<[^>]+>', '<>', r.rule) == re.sub(r'<[^>]+>', '<>', path) and methods.intersection(r.methods)]
        if collisions:
            if Config.API_COMPAT_PROFILE == 'bupt':
                for old in collisions:
                    fn = app.view_functions[rule.endpoint]
                    old_names = [x.split(':')[-1] for x in re.findall(r'<([^>]+)>', old.rule)]
                    new_names = [x.split(':')[-1] for x in re.findall(r'<([^>]+)>', path)]
                    names = dict(zip(old_names, new_names))
                    def adapted(_fn=fn, _names=names, **kwargs):
                        return _fn(**{_names.get(k, k): v for k, v in kwargs.items()})
                    app.view_functions[old.endpoint] = adapted
                if all(r.rule != path for r in collisions):
                    app.add_url_rule(path, 'bupt_root_' + rule.endpoint, fn, methods=rule.methods)
        else:
            app.add_url_rule(path, 'bupt_root_' + rule.endpoint, app.view_functions[rule.endpoint], methods=rule.methods)


register_compatibility()
