"""Flask application entry point."""

from flask import Flask
from flask_compress import Compress

from intent_hub.auth import require_auth
from intent_hub.core.components import get_component_manager

app = Flask(__name__)
Compress(app)


@app.route("/health", methods=["GET"])
def health():
    """Process-level liveness probe."""
    return {"status": "ok"}, 200


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
    from intent_hub.services.sync_task_service import get_sync_task_service

    get_sync_task_service(component_manager)

    return app
