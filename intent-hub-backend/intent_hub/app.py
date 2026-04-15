"""Flask application entry point."""

from flask import Flask
from flask_compress import Compress

from intent_hub.auth import require_auth
from intent_hub.core.components import get_component_manager

app = Flask(__name__)
Compress(app)


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


@app.route("/v1/me", methods=["GET"])
def tenant_me():
    """Tenant runtime identity."""
    from intent_hub.api import tenant

    return tenant.me()


@app.route("/v1/route", methods=["POST"])
def tenant_route():
    """Tenant runtime route API."""
    from intent_hub.api import tenant

    return tenant.route()


@app.route("/v1/dispatch", methods=["POST"])
def tenant_dispatch():
    """Tenant runtime dispatch API."""
    from intent_hub.api import tenant

    return tenant.dispatch()


@app.route("/tenant/skill-sources", methods=["GET"])
def tenant_skill_sources():
    """List tenant skill sources."""
    from intent_hub.api import tenant

    return tenant.list_skill_sources()


@app.route("/tenant/skill-sources", methods=["POST"])
def tenant_create_skill_source():
    """Create tenant skill source."""
    from intent_hub.api import tenant

    return tenant.create_skill_source()


@app.route("/tenant/skill-sources/scan", methods=["POST"])
def tenant_scan_skill_sources():
    """Scan configured tenant skill sources."""
    from intent_hub.api import tenant

    return tenant.scan_skill_sources()


@app.route("/tenant/skill-drafts", methods=["GET"])
def tenant_skill_drafts():
    """List tenant skill drafts."""
    from intent_hub.api import tenant

    return tenant.list_skill_drafts()


@app.route("/tenant/skill-drafts/apply", methods=["POST"])
def tenant_apply_skill_draft():
    """Apply one tenant skill draft."""
    from intent_hub.api import tenant

    return tenant.apply_skill_draft()


@app.route("/tenant/routes", methods=["GET"])
def tenant_get_routes():
    """List tenant routes."""
    from intent_hub.api import tenant

    return tenant.list_routes()


@app.route("/tenant/routes/search", methods=["GET"])
def tenant_search_routes():
    """Search tenant routes."""
    from intent_hub.api import tenant

    return tenant.search_routes()


@app.route("/tenant/routes", methods=["POST"])
def tenant_create_route():
    """Create tenant route."""
    from intent_hub.api import tenant

    return tenant.create_route()


@app.route("/tenant/routes/<int:route_id>", methods=["PUT"])
def tenant_update_route(route_id: int):
    """Update tenant route by ID."""
    from intent_hub.api import tenant

    return tenant.update_route(route_id)


@app.route("/tenant/routes/<int:route_id>", methods=["DELETE"])
def tenant_delete_route(route_id: int):
    """Delete tenant route by ID."""
    from intent_hub.api import tenant

    return tenant.delete_route(route_id)


@app.route("/tenant/routes/generate-utterances", methods=["POST"])
def tenant_generate_utterances():
    """Generate utterances for tenant route."""
    from intent_hub.api import tenant

    return tenant.generate_utterances()


@app.route("/tenant/routes/import-skill", methods=["POST"])
def tenant_import_route_from_skill():
    """Generate tenant route draft from SKILL.md content."""
    from intent_hub.api import tenant

    return tenant.import_route_from_skill()


@app.route("/tenant/routes/import", methods=["POST"])
def tenant_import_routes():
    """Import tenant routes from JSON (merge/replace)."""
    from intent_hub.api import tenant

    return tenant.import_routes()


@app.route("/tenant/routes/<int:route_id>/negative-samples", methods=["POST"])
def tenant_add_negative_samples(route_id: int):
    """Add tenant route negative samples."""
    from intent_hub.api import tenant

    return tenant.add_negative_samples(route_id)


@app.route("/tenant/routes/<int:route_id>/negative-samples", methods=["DELETE"])
def tenant_delete_negative_samples(route_id: int):
    """Delete tenant route negative samples."""
    from intent_hub.api import tenant

    return tenant.delete_negative_samples(route_id)


@app.route("/tenant/reindex", methods=["POST"])
def tenant_reindex():
    """Tenant reindex."""
    from intent_hub.api import tenant

    return tenant.reindex()


@app.route("/tenant/reindex/sync-route", methods=["POST"])
def tenant_sync_route():
    """Tenant sync route(s) to vector DB."""
    from intent_hub.api import tenant

    return tenant.sync_route()


@app.route("/tenant/diagnostics/overlap", methods=["GET"])
def tenant_analyze_all_overlaps():
    """Tenant overlap analysis for all routes."""
    from intent_hub.api import tenant

    return tenant.analyze_all_overlaps()


@app.route("/tenant/diagnostics/overlap/<int:route_id>", methods=["GET"])
def tenant_analyze_overlap(route_id: int):
    """Tenant overlap analysis for one route."""
    from intent_hub.api import tenant

    return tenant.analyze_overlap(route_id)


@app.route("/tenant/diagnostics/umap", methods=["GET"])
def tenant_diagnostics_umap():
    """Tenant UMAP point cloud data."""
    from intent_hub.api import tenant

    return tenant.umap_points()


@app.route("/tenant/diagnostics/repair", methods=["POST"])
def tenant_get_repair_suggestions():
    """Tenant repair suggestions."""
    from intent_hub.api import tenant

    return tenant.get_repair_suggestions()


@app.route("/tenant/diagnostics/apply-repair", methods=["POST"])
def tenant_apply_repair():
    """Apply tenant repair suggestions."""
    from intent_hub.api import tenant

    return tenant.apply_repair()


@app.route("/tenant/settings", methods=["GET"])
def tenant_get_settings():
    """Get tenant settings."""
    from intent_hub.api import tenant

    return tenant.get_settings()


@app.route("/tenant/settings", methods=["POST"])
def tenant_update_settings():
    """Update tenant settings."""
    from intent_hub.api import tenant

    return tenant.update_settings()


@app.route("/admin/tenants", methods=["GET"])
def list_tenants():
    """List platform tenants."""
    from intent_hub.api import admin

    return admin.list_tenants()


@app.route("/admin/tenants", methods=["POST"])
def create_tenant():
    """Create a tenant and initial access code."""
    from intent_hub.api import admin

    return admin.create_tenant()


@app.route("/admin/tenants/<tenant_id>/access-codes", methods=["POST"])
def create_access_code(tenant_id: str):
    """Create a tenant access code."""
    from intent_hub.api import admin

    return admin.create_access_code(tenant_id)


@app.route("/admin/tenants/<tenant_id>/access-codes/<code_id>/rotate", methods=["POST"])
def rotate_access_code(tenant_id: str, code_id: str):
    """Rotate one tenant access code."""
    from intent_hub.api import admin

    return admin.rotate_access_code(tenant_id, code_id)


@app.route("/admin/tenants/<tenant_id>/access-codes/<code_id>/disable", methods=["POST"])
def disable_access_code(tenant_id: str, code_id: str):
    """Disable one tenant access code."""
    from intent_hub.api import admin

    return admin.disable_access_code(tenant_id, code_id)


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


@app.route("/settings", methods=["POST"])
@require_auth
def update_settings():
    """Update system settings."""
    from intent_hub.api import settings

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
