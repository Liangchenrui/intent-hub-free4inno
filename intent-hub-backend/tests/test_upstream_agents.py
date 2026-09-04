import json

from intent_hub.agent_source import AgentSource
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.route_compare import comparison_detail, comparison_summary
from intent_hub.route_manager import RouteManager
from intent_hub.services.route_service import RouteService
from intent_hub.services.upstream_agent_service import UpstreamAgentService


def upstream_route(route_id, source_id, name, snapshot, overrides=None):
    return RouteConfig(
        id=route_id,
        name=name,
        route_key=f"route.{route_id}",
        description=snapshot["description"],
        utterances=snapshot["utterances"],
        negative_samples=snapshot["negative_samples"],
        source=RouteConfig.RouteSource(
            type="upstream_agent",
            source_id=source_id,
            managed_fields=["name", "description", "utterances", "negative_samples"],
            source_snapshot=snapshot,
            upstream_present=True,
        ),
        sync=RouteConfig.RouteSync(
            status="synced",
            version=1,
            synced_version=1,
            manual_overrides=overrides or [],
        ),
    )


def test_agent_source_deduplicates_labels_and_parses_corpora(monkeypatch):
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://agents.example/api/")
    monkeypatch.setattr(Config, "AGENT_API_TOKEN", "token")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "87,88")
    calls = []

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return {"code": 200, "data": self.data}

    class Session:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/resource/search"):
                return Response({"records": [{"resource": {"id": 9}}]})
            return Response(
                {
                    "id": 9,
                    "title": "Weather",
                    "text": "Forecasts",
                    "extent00": '["today", "today", "tomorrow"]',
                    "extent01": "['sports']",
                }
            )

    agents = AgentSource(Session()).fetch_all()

    assert len(agents) == 1
    assert agents[0]["utterances"] == ["today", "tomorrow"]
    assert agents[0]["negative_samples"] == ["sports"]
    assert len([call for call in calls if call[0].endswith("/detail")]) == 1
    assert all(call[1]["headers"] == {"Authorization": "Bearer token"} for call in calls)


def test_pull_preserves_overrides_allocates_local_ids_and_disables_missing(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    snapshot_a = {
        "name": "Old A",
        "description": "local description",
        "utterances": ["old"],
        "negative_samples": [],
    }
    snapshot_b = {
        "name": "Old B",
        "description": "B",
        "utterances": ["b"],
        "negative_samples": [],
    }
    route_a = upstream_route(10, "a", "Old A", snapshot_a, ["description"])
    route_a.description = "manual description"
    manager.add_route(route_a)
    manager.add_route(upstream_route(11, "b", "Old B", snapshot_b))

    incoming = [
        {
            "source_id": "a",
            "name": "New A",
            "description": "upstream description",
            "utterances": ["new"],
            "negative_samples": ["not a"],
        },
        {
            "source_id": "c",
            "name": "New A",
            "description": "C",
            "utterances": ["c"],
            "negative_samples": [],
        },
    ]
    components = type("Components", (), {"route_manager": manager})()
    service = UpstreamAgentService(
        components,
        source=type("Source", (), {"fetch_all": lambda self: incoming})(),
    )

    result = service.pull()
    routes = manager.get_all_routes()
    updated_a = next(route for route in routes if route.source.source_id == "a")
    missing_b = next(route for route in routes if route.source.source_id == "b")
    created_c = next(route for route in routes if route.source.source_id == "c")

    assert result["created"] == 1
    assert result["updated"] == 1
    assert result["preserved_overrides"] == 1
    assert result["upstream_missing"] == 1
    assert updated_a.name == "New A"
    assert updated_a.description == "manual description"
    assert updated_a.utterances == ["new"]
    assert missing_b.lifecycle_status == "disabled"
    assert missing_b.source.upstream_present is False
    assert created_c.id == 12
    assert created_c.route_key != updated_a.route_key
    assert set(result["affected_route_ids"]) == {10, 11, 12}
    assert json.loads(path.read_text(encoding="utf-8"))[0]["source"]["source_snapshot"]


def test_manual_edit_is_tracked_and_can_restore_upstream_field(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    snapshot = {
        "name": "Agent",
        "description": "upstream",
        "utterances": ["one"],
        "negative_samples": [],
    }
    original = upstream_route(3, "source-3", "Agent", snapshot)
    manager.add_route(original)
    components = type("Components", (), {"route_manager": manager})()
    edited = original.model_copy(deep=True)
    edited.description = "manual"

    saved = RouteService(components).update_route(3, edited)

    assert saved.sync.manual_overrides == ["description"]
    assert comparison_summary(saved)["status"] == "local_modified"
    detail = comparison_detail(saved)
    assert detail["fields"]["description"]["local_value"] == "manual"

    restored = UpstreamAgentService(components).restore_fields(3, ["description"])
    assert restored.description == "upstream"
    assert restored.sync.manual_overrides == []
    assert comparison_summary(restored)["status"] == "same"


def test_routes_api_exposes_upstream_summary_and_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    snapshot = {
        "name": "Agent",
        "description": "upstream",
        "utterances": ["one"],
        "negative_samples": [],
    }
    manager.add_route(upstream_route(3, "source-3", "Agent", snapshot))
    components = type("Components", (), {"route_manager": manager})()
    monkeypatch.setattr("intent_hub.api.routes.get_component_manager", lambda: components)
    monkeypatch.setattr("intent_hub.api.upstream_agents.get_component_manager", lambda: components)
    client = app.test_client()

    routes_response = client.get("/routes")
    diff_response = client.get("/routes/3/upstream-diff")

    assert routes_response.status_code == 200
    assert routes_response.get_json()[0]["comparison"]["status"] == "same"
    assert diff_response.status_code == 200
    assert diff_response.get_json()["fields"]["utterances"]["unchanged_count"] == 1
