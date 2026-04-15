from flask import g

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


class DummyPredictionService:
    def __init__(self, component_manager):
        self.component_manager = component_manager

    def predict(self, request):
        return [
            PredictResponse(
                id=12,
                name="Obsidian Wiki Builder",
                route_key="obsidian.wiki.build",
                score=0.93,
            )
        ]


def test_v1_me_returns_current_tenant_info(monkeypatch):
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())

    client = app.test_client()
    response = client.get("/v1/me", headers={"Authorization": "Bearer ih_live_team_alpha"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["tenant_id"] == "team_alpha"
    assert payload["tenant_name"] == "Team Alpha"
    assert payload["code_id"] == "ac_001"
    assert payload["code_label"] == "default"


def test_v1_route_returns_runtime_contract(monkeypatch):
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.services.prediction_service.PredictionService", DummyPredictionService)

    client = app.test_client()
    response = client.post(
        "/v1/route",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "帮我整理 wiki"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["tenant_id"] == "team_alpha"
    assert payload["route_key"] == "obsidian.wiki.build"
    assert payload["collection"] == "intent_hub_team_alpha"
    assert payload["matches"][0]["route_key"] == "obsidian.wiki.build"


def test_v1_dispatch_returns_runtime_contract(monkeypatch):
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.services.prediction_service.PredictionService", DummyPredictionService)

    client = app.test_client()
    response = client.post(
        "/v1/dispatch",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "帮我整理 wiki"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["tenant_id"] == "team_alpha"
    assert payload["route_key"] == "obsidian.wiki.build"
    assert payload["dispatch"]["status"] == "not_executed"
    assert payload["dispatch"]["suggestion"]["route_key"] == "obsidian.wiki.build"
