from intent_hub.app import app
from intent_hub.models import PredictResponse
from intent_hub.tenant.context import TenantContext


class DummyTenantAuthService:
    def authenticate_access_code(self, access_code: str):
        if access_code != "ih_live_team_alpha":
            raise ValueError("Invalid or disabled access code")

        context = TenantContext(
            tenant_id="team_alpha",
            tenant_name="Team Alpha",
            collection_name="intent_hub_team_alpha",
            workspace_dir="D:/workspace/team_alpha",
            settings_path="D:/workspace/team_alpha/settings.json",
            routes_path="D:/workspace/team_alpha/routes.json",
            diagnostics_cache_path="D:/workspace/team_alpha/diagnostics_cache.json",
            skills_index_path="D:/workspace/team_alpha/skills_index.json",
            imports_dir="D:/workspace/team_alpha/imports",
        )
        tenant = type("Tenant", (), {"tenant_id": "team_alpha", "name": "Team Alpha"})()
        code = type("AccessCode", (), {"code_id": "ac_001", "label": "default"})()
        return context, tenant, code


class DummyTenantComponentRegistry:
    def get(self, tenant_context):
        return type(
            "Manager",
            (),
            {
                "marker": tenant_context.tenant_id,
                "ensure_ready": lambda self: None,
            },
        )()


class DummyPredictionService:
    def __init__(self, component_manager):
        self.component_manager = component_manager

    def predict(self, request):
        return [
            PredictResponse(
                id=7,
                name=f"route-for-{self.component_manager.marker}",
                route_key=f"{self.component_manager.marker}.route",
                score=0.91,
            )
        ]


def test_predict_accepts_tenant_access_code(monkeypatch):
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.api.prediction.PredictionService", DummyPredictionService)
    monkeypatch.setattr(
        "intent_hub.api.prediction.get_tenant_component_registry",
        lambda: DummyTenantComponentRegistry(),
    )

    client = app.test_client()
    response = client.post(
        "/predict",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "整理 wiki"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload[0]["route_key"] == "team_alpha.route"
