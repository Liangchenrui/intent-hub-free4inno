from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory

from intent_hub.agent_source import AgentSource
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import Agent
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.services.prediction_service import PredictionService
from intent_hub.services.sync_service import SyncService


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_agent_source_fetches_search_and_details():
    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if url.endswith("/resource/search"):
                label_id = kwargs["params"]["labels"]
                return Response(
                    {
                        "code": 200,
                        "data": {
                            "records": [{"resource": {"id": 7}}]
                            if label_id in {"87", "88"}
                            else []
                        },
                    }
                )
            return Response(
                {
                    "code": 200,
                    "data": {
                        "id": 7,
                        "title": "天气 Agent",
                        "text": "查询天气",
                        "extent00": "['查天气', '明天天气']",
                        "extent01": '["写代码"]',
                    },
                }
            )

    session = Session()
    agent = AgentSource(session).fetch_all()[0]
    assert agent.utterances == ["查天气", "明天天气"]
    assert agent.negative_samples == ["写代码"]
    assert agent.details["title"] == "天气 Agent"
    assert [call[1]["params"]["labels"] for call in session.calls[:3]] == ["87", "88", "89"]
    assert len(session.calls) == 4


def test_api_requires_login_and_exposes_collection():
    client = app.test_client()
    assert client.get("/agents").status_code == 401
    login_response = client.post(
        "/auth/login",
        json={"username": Config.DEFAULT_USERNAME, "password": Config.DEFAULT_PASSWORD},
    )
    key = login_response.get_json()["api_key"]
    response = client.get("/settings", headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    assert response.get_json() == {"QDRANT_COLLECTION": Config.QDRANT_COLLECTION}


def test_sync_keeps_existing_qdrant_payload_inputs():
    agent = Agent(
        id=7,
        title="天气 Agent",
        text="查询天气",
        utterances=["查天气"],
        negative_samples=["写代码"],
        details={"id": 7, "title": "天气 Agent"},
    )

    class Encoder:
        calls = 0

        def encode(self, texts):
            self.calls += 1
            return [[float(index)] for index, _ in enumerate(texts)]

    class Qdrant:
        routes = []
        upsert_calls = 0

        def delete_routes(self, route_ids):
            self.deleted_routes = route_ids

        def upsert_routes(self, routes, batch_size):
            self.routes = routes
            self.upsert_calls += 1

        def point_ids(self, *args, **kwargs):
            return set()

        def delete_points(self, point_ids):
            self.deleted_points = point_ids

        def index_summary(self):
            return {
                "points_count": sum(
                    len(route["utterances"]) + len(route["negative_samples"])
                    for route in self.routes
                ),
                "route_ids": sorted(route["route_id"] for route in self.routes),
                "route_hashes": {route["route_id"]: route["route_hash"] for route in self.routes},
            }

    qdrant = Qdrant()
    store = SimpleNamespace(
        agents=[],
        replace=lambda agents: setattr(store, "agents", agents),
        all=lambda: store.agents,
    )
    components = SimpleNamespace(encoder=Encoder(), qdrant_client=qdrant, agent_store=store)
    source = SimpleNamespace(fetch_all=lambda: [agent])

    with TemporaryDirectory() as directory:
        state_path = Path(directory) / "sync.db"
        service = SyncService(components, source, state_path=state_path)
        result = service.sync()

        route = qdrant.routes[0]
        assert route["route_id"] == 7
        assert route["route_name"] == "天气 Agent"
        assert route["utterances"] == ["查天气"]
        assert route["score_threshold"] == 0.8
        assert route["negative_threshold"] == 0.95
        assert result["changed_agents"] == 1
        assert result["positive_points"] == 1
        assert result["negative_points"] == 1

        encoder_calls = components.encoder.calls
        assert service.sync()["changed_agents"] == 0
        assert components.encoder.calls == encoder_calls
        assert service.status()["synced"] is True

        empty_result = SyncService(
            components,
            SimpleNamespace(fetch_all=lambda: []),
            state_path=state_path,
        ).sync()
        assert empty_result["warning"] == "上游没有包含指定标签的 Agent，已保留现有索引"


def test_incremental_sync_blocks_abnormal_mass_deletion():
    agents = [
        Agent(id=index, title=str(index), utterances=[str(index)], details={"id": index})
        for index in range(10)
    ]
    store = SimpleNamespace(all=lambda: agents)
    components = SimpleNamespace(agent_store=store)
    source = SimpleNamespace(fetch_all=lambda: agents[:1])

    with TemporaryDirectory() as directory:
        service = SyncService(components, source, state_path=Path(directory) / "sync.db")
        try:
            service.sync()
        except ValueError as error:
            assert "超过安全阈值" in str(error)
        else:
            raise AssertionError("mass deletion should be blocked")


def test_full_sync_builds_and_switches_alias(monkeypatch):
    agent = Agent(id=7, title="天气 Agent", utterances=["查天气"], details={"id": 7})

    class Encoder:
        dimensions = 1

        def encode(self, texts):
            return [[1.0] for _ in texts]

    class Target:
        def upsert_routes(self, routes, batch_size):
            self.routes = routes

        def index_summary(self):
            route = self.routes[0]
            return {
                "points_count": 1,
                "route_ids": [7],
                "route_hashes": {7: route["route_hash"]},
            }

        def switch_alias(self, alias):
            self.alias = alias

    target = Target()
    store = SimpleNamespace(
        agents=[],
        replace=lambda agents: setattr(store, "agents", agents),
        all=lambda: store.agents,
    )
    components = SimpleNamespace(
        encoder=Encoder(),
        agent_store=store,
        create_qdrant=lambda collection: target,
        reset_qdrant=lambda: None,
    )

    with TemporaryDirectory() as directory:
        monkeypatch.setattr(Config, "QDRANT_COLLECTION", "agents")
        monkeypatch.setattr(Config, "SETTINGS_FILE", Path(directory) / "settings.json")
        monkeypatch.setattr(Config, "DATA_DIR", Path(directory))
        result = SyncService(
            components,
            SimpleNamespace(fetch_all=lambda: [agent]),
            state_path=Path(directory) / "sync.db",
        ).sync(mode="full")

    assert target.alias == "agents__active"
    assert result["collection"] == "agents__active"
    assert result["physical_collection"].startswith("agents__")


def test_point_ids_do_not_change_when_agent_title_changes():
    first = IntentHubQdrantClient.point_ids(7, "旧名称", ["查天气"], ["写代码"])
    renamed = IntentHubQdrantClient.point_ids(7, "新名称", ["查天气"], ["写代码"])
    legacy = IntentHubQdrantClient.point_ids(
        7, "旧名称", ["查天气"], ["写代码"], legacy=True
    )

    assert first == renamed
    assert first != legacy


def test_route_returns_best_agent_or_default_file(monkeypatch):
    agent = Agent(
        id=7,
        title="天气 Agent",
        utterances=["查天气"],
        details={"id": 7, "title": "天气 Agent"},
    )

    class Encoder:
        def encode_single(self, query):
            return [1.0]

    class Qdrant:
        def search_negative_samples(self, vector):
            return []

        def search(self, vector):
            return self.results

    qdrant = Qdrant()
    store = SimpleNamespace(get=lambda agent_id: agent if agent_id == 7 else None)
    service = PredictionService(
        SimpleNamespace(encoder=Encoder(), qdrant_client=qdrant, agent_store=store)
    )

    qdrant.results = [{"score": 0.91, "payload": {"route_id": 7}}]
    assert service.route("天气") == {
        "matched": True,
        "agent": {"id": 7, "title": "天气 Agent"},
        "score": 0.91,
        "text": None,
    }

    with TemporaryDirectory() as directory:
        default_file = Path(directory) / "default_route.txt"
        default_file.write_text("交给调用方处理", encoding="utf-8")
        monkeypatch.setattr(Config, "DEFAULT_ROUTE_FILE", default_file)
        qdrant.results = [{"score": 0.79, "payload": {"route_id": 7}}]
        assert service.route("未知问题") == {
            "matched": False,
            "agent": None,
            "score": None,
            "text": "交给调用方处理",
        }


def test_route_api_uses_consistent_error_envelope():
    client = app.test_client()

    unauthorized = client.post("/route", json={"query": "天气"})
    assert unauthorized.status_code == 401
    assert unauthorized.get_json() == {
        "success": False,
        "data": None,
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Authentication failed",
            "detail": None,
        },
    }

    login_response = client.post(
        "/auth/login",
        json={"username": Config.DEFAULT_USERNAME, "password": Config.DEFAULT_PASSWORD},
    )
    key = login_response.get_json()["api_key"]
    invalid = client.post(
        "/route",
        json={"query": ""},
        headers={"Authorization": f"Bearer {key}"},
    )
    assert invalid.status_code == 400
    payload = invalid.get_json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "INVALID_REQUEST"
