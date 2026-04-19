from intent_hub.app import app
from intent_hub.models import RouteConfig
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


class DummyRouteManager:
    def __init__(self):
        self.route = RouteConfig(
            id=12,
            name="Obsidian Wiki Builder",
            route_key="obsidian.wiki.build",
            description="",
            utterances=["整理 wiki"],
            negative_samples=["播放音乐"],
            score_threshold=0.75,
            negative_threshold=0.95,
        )
        self.saved_route = None

    def get_route(self, route_id: int):
        if route_id == self.route.id:
            return self.route
        return None

    def add_route(self, route):
        self.saved_route = route
        self.route = route


class DummyTenantComponentManager:
    def __init__(self):
        self.route_manager = DummyRouteManager()
        self.synced_route_ids = []

    def ensure_ready(self):
        return None


class DummyTenantComponentRegistry:
    def __init__(self):
        self.manager = DummyTenantComponentManager()

    def get(self, tenant_context):
        return self.manager


def test_positive_feedback_appends_utterance_without_sync(monkeypatch):
    registry = DummyTenantComponentRegistry()
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_component_registry", lambda: registry)

    client = app.test_client()
    response = client.post(
        "/tenant/routes/12/feedback/positive",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "帮我整理知识库"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "帮我整理知识库" in registry.manager.route_manager.route.utterances
    assert registry.manager.synced_route_ids == []
    assert payload["route_id"] == 12
    assert payload["total_utterances"] == 2
    assert "sync_result" not in payload


def test_negative_feedback_appends_negative_sample_without_sync(monkeypatch):
    registry = DummyTenantComponentRegistry()
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_component_registry", lambda: registry)

    client = app.test_client()
    response = client.post(
        "/tenant/routes/12/feedback/negative",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "帮我播放音乐"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "帮我播放音乐" in registry.manager.route_manager.route.negative_samples
    assert registry.manager.synced_route_ids == []
    assert payload["route_id"] == 12
    assert payload["total_negative_samples"] == 2
    assert "sync_result" not in payload


def test_delete_positive_feedback_removes_utterance_without_sync(monkeypatch):
    registry = DummyTenantComponentRegistry()
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_component_registry", lambda: registry)

    client = app.test_client()
    response = client.delete(
        "/tenant/routes/12/feedback/positive",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "整理 wiki"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "整理 wiki" not in registry.manager.route_manager.route.utterances
    assert registry.manager.synced_route_ids == []
    assert payload["route_id"] == 12
    assert payload["total_utterances"] == 0


def test_delete_negative_feedback_removes_negative_sample_without_sync(monkeypatch):
    registry = DummyTenantComponentRegistry()
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_component_registry", lambda: registry)

    client = app.test_client()
    response = client.delete(
        "/tenant/routes/12/feedback/negative",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"text": "播放音乐"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "播放音乐" not in registry.manager.route_manager.route.negative_samples
    assert registry.manager.synced_route_ids == []
    assert payload["route_id"] == 12
    assert payload["total_negative_samples"] == 0


def test_delete_positive_feedback_accepts_query_param(monkeypatch):
    registry = DummyTenantComponentRegistry()
    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService())
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_component_registry", lambda: registry)

    client = app.test_client()
    response = client.delete(
        "/tenant/routes/12/feedback/positive?text=%E6%95%B4%E7%90%86%20wiki",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "整理 wiki" not in registry.manager.route_manager.route.utterances
    assert payload["route_id"] == 12
    assert payload["total_utterances"] == 0
