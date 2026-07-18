from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory

from intent_hub.agent_source import AgentSource
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import Agent
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
        def encode(self, texts):
            return [[float(index)] for index, _ in enumerate(texts)]

    class Qdrant:
        def delete_all(self):
            self.deleted = True

        def upsert_route_utterances(self, **kwargs):
            self.positive = kwargs

        def upsert_route_negative_samples(self, **kwargs):
            self.negative = kwargs

    qdrant = Qdrant()
    store = SimpleNamespace(
        agents=[],
        replace=lambda agents: setattr(store, "agents", agents),
        all=lambda: store.agents,
    )
    components = SimpleNamespace(encoder=Encoder(), qdrant_client=qdrant, agent_store=store)
    source = SimpleNamespace(fetch_all=lambda: [agent])

    result = SyncService(components, source).sync()

    assert qdrant.positive["route_id"] == 7
    assert qdrant.positive["route_name"] == "天气 Agent"
    assert qdrant.positive["utterances"] == ["查天气"]
    assert qdrant.positive["score_threshold"] == 0.8
    assert qdrant.negative["negative_threshold"] == 0.95
    assert result == {
        "agents_count": 1,
        "indexed_agents_count": 1,
        "positive_points": 1,
        "negative_points": 1,
    }
    qdrant.index_summary = lambda: {
        "points_count": 2,
        "route_ids": [7],
        "route_hashes": {7: qdrant.positive["route_hash"]},
    }
    assert SyncService(components, source).status()["synced"] is True
    empty_result = SyncService(components, SimpleNamespace(fetch_all=lambda: [])).sync()
    assert empty_result["warning"] == "上游没有包含指定标签的 Agent"


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
