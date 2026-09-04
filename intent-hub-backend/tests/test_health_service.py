from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.services.health_service import check_external_services


class Response:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400


def test_external_service_health_checks_embedding_and_qdrant(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(200)

    monkeypatch.setattr(Config, "EMBEDDING_SERVICE_URL", "http://embedding.example/embed")
    monkeypatch.setattr(Config, "QDRANT_URL", "http://qdrant.example:6333")
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "secret")
    monkeypatch.setattr("intent_hub.services.health_service.requests.get", get)

    result = check_external_services()

    assert result["status"] == "ok"
    assert result["services"]["embedding"]["healthy"] is True
    assert result["services"]["qdrant"]["healthy"] is True
    assert ("http://embedding.example/health", {"headers": {}, "timeout": 5}) in calls
    assert (
        "http://qdrant.example:6333/healthz",
        {"headers": {"api-key": "secret"}, "timeout": 5},
    ) in calls


def test_external_service_health_endpoint(monkeypatch):
    expected = {
        "status": "degraded",
        "services": {
            "embedding": {"healthy": True},
            "qdrant": {"healthy": False},
        },
    }
    monkeypatch.setattr("intent_hub.app.check_external_services", lambda: expected)

    response = app.test_client().get("/health/services")

    assert response.status_code == 200
    assert response.get_json() == expected
