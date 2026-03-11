"""Flask application entry point."""

from flask import Flask
from flask_compress import Compress

from intent_hub.api import (
    auth,
    diagnostics,
    prediction,
    reindex,
    routes,
    settings,
)
from intent_hub.auth import require_auth
from intent_hub.core.components import get_component_manager

app = Flask(__name__)
Compress(app)


@app.route("/auth/login", methods=["POST"])
def login():
    """Login (no auth required)."""
    return auth.login()


@app.route("/predict", methods=["POST"])
def predict():
    """Route prediction (Telestar auth)."""
    return prediction.predict()


@app.route("/routes", methods=["GET"])
@require_auth
def get_routes():
    """List all routes."""
    return routes.get_routes()


@app.route("/routes/search", methods=["GET"])
@require_auth
def search_routes():
    """Search routes."""
    return routes.search_routes()


@app.route("/routes", methods=["POST"])
@require_auth
def create_route():
    """Create route."""
    return routes.create_route()


@app.route("/routes/<int:route_id>", methods=["PUT"])
@require_auth
def update_route(route_id: int):
    """Update route by ID."""
    return routes.update_route(route_id)


@app.route("/routes/<int:route_id>", methods=["DELETE"])
@require_auth
def delete_route(route_id: int):
    """Delete route by ID."""
    return routes.delete_route(route_id)


@app.route("/routes/generate-utterances", methods=["POST"])
@require_auth
def generate_utterances():
    """Generate utterances from Agent info."""
    return routes.generate_utterances()


@app.route("/routes/import", methods=["POST"])
@require_auth
def import_routes():
    """Import routes from JSON (merge/replace)."""
    return routes.import_routes()


@app.route("/routes/<int:route_id>/negative-samples", methods=["POST"])
@require_auth
def add_negative_samples(route_id: int):
    """Add Negative Utterances for route."""
    return routes.add_negative_samples(route_id)


@app.route("/routes/<int:route_id>/negative-samples", methods=["DELETE"])
@require_auth
def delete_negative_samples(route_id: int):
    """Delete all Negative Utterances for route."""
    return routes.delete_negative_samples(route_id)


@app.route("/reindex", methods=["POST"])
@require_auth
def reindex_route():
    """Reindex."""
    return reindex.reindex()


@app.route("/reindex/sync-route", methods=["POST"])
@require_auth
def sync_route():
    """Sync one or more routes to vector DB."""
    return reindex.sync_route()


@app.route("/diagnostics/overlap", methods=["GET"])
@require_auth
def analyze_all_overlaps():
    """Analyze overlap for all routes."""
    return diagnostics.analyze_all_overlaps()


@app.route("/diagnostics/overlap/<int:route_id>", methods=["GET"])
@require_auth
def analyze_overlap(route_id: int):
    """Analyze overlap for one route."""
    return diagnostics.analyze_overlap(route_id)


@app.route("/diagnostics/umap", methods=["GET"])
@require_auth
def diagnostics_umap():
    """UMAP point cloud data."""
    return diagnostics.umap_points()


@app.route("/diagnostics/repair", methods=["POST"])
@require_auth
def get_repair_suggestions():
    """Get LLM repair suggestions."""
    return diagnostics.get_repair_suggestions()


@app.route("/diagnostics/apply-repair", methods=["POST"])
@require_auth
def apply_repair():
    """Apply repair suggestions."""
    return diagnostics.apply_repair()


@app.route("/settings", methods=["GET"])
@require_auth
def get_settings():
    """Get system settings."""
    return settings.get_settings()


@app.route("/settings", methods=["POST"])
@require_auth
def update_settings():
    """Update system settings."""
    return settings.update_settings()


def init_app():
    """Initialize app (including components)."""
    component_manager = get_component_manager()
    component_manager.init_components()

    try:
        from intent_hub.services.diagnostic_service import DiagnosticService
        from intent_hub.utils.logger import logger

        diagnostic_service = DiagnosticService(component_manager)
        diagnostic_service.run_async_diagnostics("full")
        logger.info("Async full diagnostics started")
    except Exception as e:
        from intent_hub.utils.logger import logger

        logger.error(f"Failed to start diagnostics: {e}")

    return app
