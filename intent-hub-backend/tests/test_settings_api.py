from intent_hub.api import settings
from intent_hub.app import app
from intent_hub.config import Config


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "result": {
                "collections": [
                    {"name": "z_collection"},
                    {"name": "a_collection"},
                ]
            }
        }


def test_list_qdrant_collections_uses_configured_url(monkeypatch):
    calls = {}
    monkeypatch.setattr(Config, "QDRANT_URL", "http://qdrant.example.com/base/")
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "secret")

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(settings.requests, "get", fake_get)

    with app.test_request_context():
        response, status = settings.list_qdrant_collections()

    assert status == 200
    assert response.get_json() == {"items": ["a_collection", "z_collection"]}
    assert calls == {
        "url": "http://qdrant.example.com/base/collections",
        "headers": {"api-key": "secret"},
        "timeout": 10,
    }
