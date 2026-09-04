from types import SimpleNamespace

from intent_hub.agent_store import AgentStore
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import Agent
from intent_hub.services.collection_service import CollectionService


class FakeQdrantClient:
    def __init__(self, points=None):
        self.points = points or []

    def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name="routes")])

    def get_aliases(self):
        return SimpleNamespace(aliases=[SimpleNamespace(alias_name="routes__active", collection_name="routes")])

    def scroll(self, **kwargs):
        return self.points, None


def test_lists_collections_and_aliases(monkeypatch):
    service = CollectionService(SimpleNamespace())
    monkeypatch.setattr(service, "_client", lambda: FakeQdrantClient())

    result = service.list_collections()

    assert [item["name"] for item in result["collections"]] == ["routes", "routes__active"]
    assert result["collections"][1]["target"] == "routes"


def test_restores_agent_text_from_qdrant_payload(tmp_path, monkeypatch):
    store = AgentStore(tmp_path / "agents.db")
    store.upsert(Agent(id=7, title="原名称", utterances=["旧语料"]))
    points = [
        SimpleNamespace(payload={"route_id": 7, "route_name": "天气", "utterance": "查天气", "score_threshold": 0.8}),
        SimpleNamespace(payload={"route_id": 7, "route_name": "天气", "utterance": "写代码", "is_negative": True, "negative_threshold": 0.95}),
    ]
    components = SimpleNamespace(agent_store=store, reset_qdrant=lambda: None)
    service = CollectionService(components)
    monkeypatch.setattr(service, "_client", lambda: FakeQdrantClient(points))
    monkeypatch.setattr(Config, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(Config, "QDRANT_COLLECTION", "before_restore")

    result = service.restore_collection("routes")

    restored = store.get(7)
    assert restored.title == "天气"
    assert restored.utterances == ["查天气"]
    assert restored.negative_samples == ["写代码"]
    assert result["restored_agents"] == 1
    assert result["positive_texts"] == 1
    assert result["negative_texts"] == 1


def test_collection_api_requires_auth_and_returns_options(monkeypatch):
    expected = {"current": "routes", "collections": []}
    monkeypatch.setattr(
        "intent_hub.app.CollectionService.list_collections",
        lambda self: expected,
    )
    client = app.test_client()

    assert client.get("/collections").status_code == 401
    response = client.get(
        "/collections",
        headers={"Authorization": f"Bearer {Config.AUTH_CODE}"},
    )
    assert response.status_code == 200
    assert response.get_json() == expected
