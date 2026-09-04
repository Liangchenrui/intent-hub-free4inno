from intent_hub.api import settings
from intent_hub.app import app
from intent_hub.config import Config


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_list_qdrant_collections_uses_configured_url(monkeypatch):
    calls = []
    monkeypatch.setattr(Config, "QDRANT_URL", "http://qdrant.example.com/base/")
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "secret")

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/aliases"):
            return FakeResponse({"result": {"aliases": [{"alias_name": "active", "collection_name": "a_collection"}]}})
        return FakeResponse({"result": {"collections": [{"name": "z_collection"}, {"name": "a_collection"}]}})

    monkeypatch.setattr("intent_hub.services.collection_service.requests.get", fake_get)

    with app.test_request_context():
        response, status = settings.list_qdrant_collections()

    assert status == 200
    payload = response.get_json()
    assert payload["items"] == ["a_collection", "active", "z_collection"]
    assert payload["collections"][1] == {"name": "active", "kind": "alias", "target": "a_collection"}
    assert [call[0] for call in calls] == [
        "http://qdrant.example.com/base/collections",
        "http://qdrant.example.com/base/aliases",
    ]
    assert all(call[1] == {"headers": {"api-key": "secret"}, "timeout": 10} for call in calls)
